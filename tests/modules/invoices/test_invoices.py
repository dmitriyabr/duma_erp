import pytest
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import func, select
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.invoices.models import Invoice, InvoiceStatus, InvoiceType
from src.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceFilters,
    InvoiceLineCreate,
)
from src.modules.invoices.service import InvoiceService
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.students.models import Grade, Student, StudentStatus, Gender
from src.modules.terms.models import Term, TermStatus, PriceSetting, TransportZone, TransportPricing


class TestInvoiceService:
    """Tests for InvoiceService."""

    async def _setup_test_data(self, db_session: AsyncSession) -> dict:
        """Create test data for invoice tests."""
        # Create user first
        from src.core.auth.service import AuthService
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="test@school.com",
            password="Test123!",
            full_name="Test User",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.flush()

        # Create category
        category = Category(name="Test Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        # Create kits
        school_fee_kit = Kit(
            category_id=category.id,
            sku_code="SCH-FEE",
            name="School Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.BY_GRADE.value,
            price=None,
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(school_fee_kit)

        transport_fee_kit = Kit(
            category_id=category.id,
            sku_code="TRN-FEE",
            name="Transport Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.BY_ZONE.value,
            price=None,
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(transport_fee_kit)

        standard_kit = Kit(
            category_id=category.id,
            sku_code="STD-ITEM",
            name="Standard Item",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(standard_kit)

        admission_fee_kit = Kit(
            category_id=category.id,
            sku_code="ADMISSION-FEE",
            name="Admission Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("5000.00"),
            requires_full_payment=True,
            is_active=True,
        )
        interview_fee_kit = Kit(
            category_id=category.id,
            sku_code="INTERVIEW-FEE",
            name="Interview Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            requires_full_payment=True,
            is_active=True,
        )
        db_session.add(admission_fee_kit)
        db_session.add(interview_fee_kit)
        await db_session.flush()

        # Create grade
        grade = Grade(code="TST", name="Test Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        # Create transport zone
        zone = TransportZone(zone_name="Test Zone", zone_code="TZ", is_active=True)
        db_session.add(zone)
        await db_session.flush()

        # Create term
        term = Term(
            year=2026,
            term_number=1,
            display_name="Term 1 2026",
            status=TermStatus.ACTIVE.value,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            created_by_id=user.id,
        )
        db_session.add(term)
        await db_session.flush()

        # Create price setting
        price_setting = PriceSetting(
            term_id=term.id,
            grade=grade.code,
            school_fee_amount=Decimal("15000.00"),
        )
        db_session.add(price_setting)

        # Create transport pricing
        transport_pricing = TransportPricing(
            term_id=term.id,
            zone_id=zone.id,
            transport_fee_amount=Decimal("5000.00"),
        )
        db_session.add(transport_pricing)
        await db_session.flush()

        # Create student
        student = Student(
            student_number="STU-2026-000001",
            first_name="Test",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            transport_zone_id=zone.id,
            guardian_name="Test Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        # Create student without transport
        student_no_transport = Student(
            student_number="STU-2026-000002",
            first_name="No",
            last_name="Transport",
            gender=Gender.FEMALE.value,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Guardian",
            guardian_phone="+254712345679",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student_no_transport)
        await db_session.flush()

        await db_session.commit()

        return {
            "user": user,
            "category": category,
            "school_fee_kit": school_fee_kit,
            "transport_fee_kit": transport_fee_kit,
            "standard_kit": standard_kit,
            "admission_fee_kit": admission_fee_kit,
            "interview_fee_kit": interview_fee_kit,
            "grade": grade,
            "zone": zone,
            "term": term,
            "student": student,
            "student_no_transport": student_no_transport,
        }

    async def test_create_adhoc_invoice(self, db_session: AsyncSession):
        """Test creating an ad-hoc invoice."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(
                        kit_id=data["standard_kit"].id,
                        quantity=2,
                    )
                ],
            ),
            created_by_id=data["user"].id,
        )

        assert invoice.id is not None
        assert invoice.invoice_number.startswith("INV-")
        assert invoice.invoice_type == InvoiceType.ADHOC.value
        assert invoice.status == InvoiceStatus.DRAFT.value
        assert len(invoice.lines) == 1
        assert invoice.subtotal == Decimal("1000.00")  # 500 * 2
        assert invoice.total == Decimal("1000.00")
        assert invoice.amount_due == Decimal("1000.00")

    async def test_add_line_to_invoice(self, db_session: AsyncSession):
        """Test adding a line to a draft invoice."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(student_id=data["student"].id),
            created_by_id=data["user"].id,
        )

        invoice = await service.add_line(
            invoice.id,
            InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1),
            added_by_id=data["user"].id,
        )

        assert len(invoice.lines) == 1
        assert invoice.total == Decimal("500.00")

    async def test_remove_line_from_invoice(self, db_session: AsyncSession):
        """Test removing a line from a draft invoice."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        line_id = invoice.lines[0].id
        invoice = await service.remove_line(invoice.id, line_id, removed_by_id=data["user"].id)

        assert len(invoice.lines) == 0
        assert invoice.total == Decimal("0.00")

    async def test_cannot_add_line_to_issued_invoice(self, db_session: AsyncSession):
        """Test that lines cannot be added to issued invoices."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        await service.issue_invoice(invoice.id, issued_by_id=data["user"].id)

        with pytest.raises(ValidationError):
            await service.add_line(
                invoice.id,
                InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1),
                added_by_id=data["user"].id,
            )

    async def test_issue_invoice(self, db_session: AsyncSession):
        """Test issuing a draft invoice."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        invoice = await service.issue_invoice(invoice.id, issued_by_id=data["user"].id)

        assert invoice.status == InvoiceStatus.ISSUED.value
        assert invoice.issue_date == date.today()
        assert invoice.due_date == date.today() + timedelta(days=30)

    async def test_issue_invoice_creates_reservation_for_product_kit(
        self, db_session: AsyncSession
    ):
        """Test that issuing an invoice with product kit creates reservation immediately."""
        data = await self._setup_test_data(db_session)
        
        # Create a product kit (not service)
        from src.modules.items.models import Item, KitItem
        from src.modules.inventory.service import InventoryService
        from src.modules.inventory.schemas import ReceiveStockRequest
        
        product_item = Item(
            category_id=data["category"].id,
            sku_code="PROD-ITEM-001",
            name="Product Item",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            is_active=True,
        )
        db_session.add(product_item)
        await db_session.flush()

        product_kit = Kit(
            category_id=data["category"].id,
            sku_code="PROD-KIT-001",
            name="Product Kit",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(product_kit)
        await db_session.flush()

        kit_item = KitItem(
            kit_id=product_kit.id,
            item_id=product_item.id,
            quantity=1,
        )
        db_session.add(kit_item)
        await db_session.flush()

        # Receive stock
        inventory = InventoryService(db_session)
        await inventory.receive_stock(
            ReceiveStockRequest(
                item_id=product_item.id,
                quantity=10,
                unit_cost=Decimal("200.00"),
                reference_type="test",
                reference_id=1,
                notes="Initial stock",
            ),
            received_by_id=data["user"].id,
        )

        # Create invoice with product kit
        service = InvoiceService(db_session)
        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=product_kit.id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        # Issue invoice (should create reservation via router, but we test service directly)
        invoice = await service.issue_invoice(invoice.id, issued_by_id=data["user"].id)
        
        # Sync reservations (this is called in router after issue)
        from src.modules.reservations.service import ReservationService
        reservation_service = ReservationService(db_session)
        await reservation_service.sync_for_invoice(invoice.id, user_id=data["user"].id)
        await db_session.commit()

        # Check that reservation was created
        line = invoice.lines[0]
        reservation = await reservation_service.get_by_invoice_line_id(line.id)
        assert reservation is not None
        assert reservation.invoice_line_id == line.id
        assert reservation.status == "pending"

    async def test_create_invoice_with_editable_kit_and_components(
        self, db_session: AsyncSession
    ):
        """Test creating an invoice with editable kit and custom components."""
        data = await self._setup_test_data(db_session)
        
        # Create product items
        from src.modules.items.models import Item, KitItem
        from src.modules.inventory.service import InventoryService
        from src.modules.inventory.schemas import ReceiveStockRequest
        
        item_s = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-S",
            name="Shirt Size S",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_s)
        await db_session.flush()

        item_m = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-M",
            name="Shirt Size M",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_m)
        await db_session.flush()

        # Create editable kit
        editable_kit = Kit(
            category_id=data["category"].id,
            sku_code="UNIFORM-S",
            name="Uniform Kit S",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("90.00"),
            is_editable_components=True,
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(editable_kit)
        await db_session.flush()

        # Add default items to kit
        kit_item = KitItem(
            kit_id=editable_kit.id,
            item_id=item_s.id,
            quantity=1,
            source_type="item",
        )
        db_session.add(kit_item)
        await db_session.flush()

        # Receive stock
        inventory = InventoryService(db_session)
        await inventory.receive_stock(
            ReceiveStockRequest(
                item_id=item_s.id,
                quantity=10,
                unit_cost=Decimal("30.00"),
                reference_type="test",
                reference_id=1,
                notes="Initial stock",
            ),
            received_by_id=data["user"].id,
        )
        await inventory.receive_stock(
            ReceiveStockRequest(
                item_id=item_m.id,
                quantity=10,
                unit_cost=Decimal("30.00"),
                reference_type="test",
                reference_id=1,
                notes="Initial stock",
            ),
            received_by_id=data["user"].id,
        )

        # Create invoice with editable kit and custom components
        service = InvoiceService(db_session)
        from src.modules.invoices.schemas import InvoiceLineComponentInput

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(
                        kit_id=editable_kit.id,
                        quantity=1,
                        components=[
                            InvoiceLineComponentInput(item_id=item_m.id, quantity=1)  # Changed from S to M
                        ],
                    )
                ],
            ),
            created_by_id=data["user"].id,
        )

        assert invoice.id is not None
        assert len(invoice.lines) == 1
        line = invoice.lines[0]
        assert line.kit_id == editable_kit.id
        
        # Check that components were saved
        assert len(line.components) == 1
        assert line.components[0].item_id == item_m.id  # Changed to M
        assert line.components[0].quantity == 1

    async def test_reservation_uses_components_for_editable_kit(
        self, db_session: AsyncSession
    ):
        """Test that reservation uses InvoiceLineComponent items for editable kits."""
        data = await self._setup_test_data(db_session)
        
        # Create product items
        from src.modules.items.models import Item, KitItem
        from src.modules.inventory.service import InventoryService
        from src.modules.inventory.schemas import ReceiveStockRequest
        
        item_s = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-S",
            name="Shirt Size S",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_s)
        await db_session.flush()

        item_m = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-M",
            name="Shirt Size M",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_m)
        await db_session.flush()

        # Create editable kit with default item S
        editable_kit = Kit(
            category_id=data["category"].id,
            sku_code="UNIFORM-S",
            name="Uniform Kit S",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("90.00"),
            is_editable_components=True,
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(editable_kit)
        await db_session.flush()

        kit_item = KitItem(
            kit_id=editable_kit.id,
            item_id=item_s.id,
            quantity=1,
            source_type="item",
        )
        db_session.add(kit_item)
        await db_session.flush()

        # Receive stock
        inventory = InventoryService(db_session)
        await inventory.receive_stock(
            ReceiveStockRequest(
                item_id=item_s.id,
                quantity=10,
                unit_cost=Decimal("30.00"),
                reference_type="test",
                reference_id=1,
                notes="Initial stock",
            ),
            received_by_id=data["user"].id,
        )
        await inventory.receive_stock(
            ReceiveStockRequest(
                item_id=item_m.id,
                quantity=10,
                unit_cost=Decimal("30.00"),
                reference_type="test",
                reference_id=1,
                notes="Initial stock",
            ),
            received_by_id=data["user"].id,
        )

        # Create invoice with editable kit, custom component (M instead of S)
        service = InvoiceService(db_session)
        from src.modules.invoices.schemas import InvoiceLineComponentInput

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(
                        kit_id=editable_kit.id,
                        quantity=1,
                        components=[
                            InvoiceLineComponentInput(item_id=item_m.id, quantity=1)  # Changed to M
                        ],
                    )
                ],
            ),
            created_by_id=data["user"].id,
        )

        # Issue invoice
        invoice = await service.issue_invoice(invoice.id, issued_by_id=data["user"].id)
        
        # Sync reservations
        from src.modules.reservations.service import ReservationService
        reservation_service = ReservationService(db_session)
        await reservation_service.sync_for_invoice(invoice.id, user_id=data["user"].id)
        await db_session.commit()

        # Check that reservation uses component item (M), not default kit item (S)
        line = invoice.lines[0]
        reservation = await reservation_service.get_by_invoice_line_id(line.id)
        assert reservation is not None
        assert len(reservation.items) == 1
        assert reservation.items[0].item_id == item_m.id  # Should be M, not S
        assert reservation.items[0].quantity_required == 1

    async def test_validate_component_item_belongs_to_variant(
        self, db_session: AsyncSession
    ):
        """Test that component item must belong to the same variant as kit's default item."""
        data = await self._setup_test_data(db_session)
        
        # Create product items
        from src.modules.items.models import Item, KitItem
        from src.modules.items.service import ItemService
        from src.modules.inventory.service import InventoryService
        from src.modules.inventory.schemas import ReceiveStockRequest
        
        item_s = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-S",
            name="Shirt Size S",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_s)
        await db_session.flush()

        item_m = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-M",
            name="Shirt Size M",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_m)
        await db_session.flush()

        item_xl = Item(
            category_id=data["category"].id,
            sku_code="SHIRT-XL",
            name="Shirt Size XL",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("50.00"),
            is_active=True,
        )
        db_session.add(item_xl)
        await db_session.flush()

        # Create variant with S and M only
        from src.modules.items.schemas import ItemVariantCreate
        item_service = ItemService(db_session)
        variant = await item_service.create_variant(
            ItemVariantCreate(name="Shirt Sizes S-M", item_ids=[item_s.id, item_m.id]),
            created_by_id=data["user"].id,
        )

        # Create editable kit with variant component
        editable_kit = Kit(
            category_id=data["category"].id,
            sku_code="UNIFORM-S",
            name="Uniform Kit S",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("90.00"),
            is_editable_components=True,
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(editable_kit)
        await db_session.flush()

        kit_item = KitItem(
            kit_id=editable_kit.id,
            variant_id=variant.id,
            default_item_id=item_s.id,
            quantity=1,
            source_type="variant",
        )
        db_session.add(kit_item)
        await db_session.flush()

        # Try to create invoice with XL (not in variant) - should fail
        service = InvoiceService(db_session)
        from src.modules.invoices.schemas import InvoiceLineComponentInput
        from src.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="does not belong to the same variant"):
            await service.create_adhoc_invoice(
                InvoiceCreate(
                    student_id=data["student"].id,
                    lines=[
                        InvoiceLineCreate(
                            kit_id=editable_kit.id,
                            quantity=1,
                            components=[
                                InvoiceLineComponentInput(item_id=item_xl.id, quantity=1)  # XL not in variant
                            ],
                        )
                    ],
                ),
                created_by_id=data["user"].id,
            )

        # Create invoice with M (in variant) - should succeed
        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(
                        kit_id=editable_kit.id,
                        quantity=1,
                        components=[
                            InvoiceLineComponentInput(item_id=item_m.id, quantity=1)  # M is in variant
                        ],
                    )
                ],
            ),
            created_by_id=data["user"].id,
        )

        assert invoice.id is not None
        assert len(invoice.lines[0].components) == 1
        assert invoice.lines[0].components[0].item_id == item_m.id

    async def test_cancel_invoice(self, db_session: AsyncSession):
        """Test cancelling an unpaid invoice."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )
        await service.issue_invoice(invoice.id, issued_by_id=data["user"].id)

        invoice = await service.cancel_invoice(invoice.id, cancelled_by_id=data["user"].id)

        assert invoice.status == InvoiceStatus.CANCELLED.value

    async def test_prevent_duplicate_admission_fee(self, db_session: AsyncSession):
        """Admission fee can only be billed once per student."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["admission_fee_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        with pytest.raises(ValidationError):
            await service.add_line(
                invoice.id,
                InvoiceLineCreate(kit_id=data["admission_fee_kit"].id, quantity=1),
                added_by_id=data["user"].id,
            )

    async def test_cancel_draft_invoice(self, db_session: AsyncSession):
        """Test cancelling a draft invoice without issuing."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        invoice = await service.cancel_invoice(invoice.id, cancelled_by_id=data["user"].id)

        assert invoice.status == InvoiceStatus.CANCELLED.value

    async def test_update_line_discount(self, db_session: AsyncSession):
        """Test updating discount on a line."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        invoice = await service.create_adhoc_invoice(
            InvoiceCreate(
                student_id=data["student"].id,
                lines=[
                    InvoiceLineCreate(kit_id=data["standard_kit"].id, quantity=1)
                ],
            ),
            created_by_id=data["user"].id,
        )

        line_id = invoice.lines[0].id
        invoice = await service.update_line_discount(
            invoice.id, line_id, Decimal("100.00"), updated_by_id=data["user"].id
        )

        assert invoice.lines[0].discount_amount == Decimal("100.00")
        assert invoice.lines[0].net_amount == Decimal("400.00")
        assert invoice.discount_total == Decimal("100.00")
        assert invoice.total == Decimal("400.00")

    async def test_generate_term_invoices(self, db_session: AsyncSession):
        """Test generating term invoices for all active students."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        result = await service.generate_term_invoices(data["term"].id, generated_by_id=data["user"].id)

        assert result.school_fee_invoices_created == 2  # Both students
        assert result.transport_invoices_created == 1  # Only student with transport
        assert result.students_skipped == 0
        assert result.total_students_processed == 2

        # Verify invoices were created
        filters = InvoiceFilters(term_id=data["term"].id)
        invoices, total = await service.list_invoices(filters)
        assert total == 5  # 2 school fee + 1 transport + 2 admission/interview

        adhoc_result = await db_session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(
                Invoice.term_id == data["term"].id,
                Invoice.invoice_type == InvoiceType.ADHOC.value,
            )
        )
        assert (adhoc_result.scalar() or 0) == 2

    async def test_generate_term_invoices_skips_existing(self, db_session: AsyncSession):
        """Test that regenerating term invoices skips existing ones."""
        data = await self._setup_test_data(db_session)
        service = InvoiceService(db_session)

        # First generation
        await service.generate_term_invoices(data["term"].id, generated_by_id=data["user"].id)

        # Second generation should skip
        result = await service.generate_term_invoices(data["term"].id, generated_by_id=data["user"].id)

        assert result.school_fee_invoices_created == 0
        assert result.transport_invoices_created == 0
        assert result.students_skipped == 2


class TestInvoiceEndpoints:
    """Tests for invoice API endpoints."""

    async def _setup_auth_and_data(
        self, db_session: AsyncSession
    ) -> tuple[str, int, dict]:
        """Create super admin and test data."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="superadmin@school.com",
            password="SuperAdmin123",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        _, access_token, _ = await auth_service.authenticate(
            "superadmin@school.com", "SuperAdmin123"
        )

        # Create test data
        category = Category(name="API Test Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        kit = Kit(
            category_id=category.id,
            sku_code="API-ITEM",
            name="API Test Item",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(kit)

        grade = Grade(code="API", name="API Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-API-000001",
            first_name="API",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="API Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()
        await db_session.commit()

        return access_token, user.id, {"kit": kit, "student": student}

    async def test_create_invoice(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating an invoice via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        response = await client.post(
            "/api/v1/invoices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "lines": [
                    {"kit_id": data["kit"].id, "quantity": 1}
                ],
            },
        )

        assert response.status_code == 201
        result = response.json()
        assert result["success"] is True
        assert result["data"]["invoice_number"].startswith("INV-")
        assert result["data"]["status"] == "draft"
        assert len(result["data"]["lines"]) == 1

    async def test_list_invoices(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing invoices via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        # Create an invoice first
        await client.post(
            "/api/v1/invoices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "lines": [{"kit_id": data["kit"].id, "quantity": 1}],
            },
        )

        response = await client.get(
            "/api/v1/invoices",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["data"]["total"] >= 1

    async def test_issue_invoice_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test issuing an invoice via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        # Create invoice
        create_response = await client.post(
            "/api/v1/invoices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "lines": [{"kit_id": data["kit"].id, "quantity": 1}],
            },
        )
        invoice_id = create_response.json()["data"]["id"]

        # Issue invoice
        response = await client.post(
            f"/api/v1/invoices/{invoice_id}/issue",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["status"] == "issued"

    async def test_update_line_discount_api(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test updating line discount via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        # Create invoice
        create_response = await client.post(
            "/api/v1/invoices",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "lines": [{"kit_id": data["kit"].id, "quantity": 1}],
            },
        )
        invoice_data = create_response.json()["data"]
        invoice_id = invoice_data["id"]
        line_id = invoice_data["lines"][0]["id"]

        # Update discount
        response = await client.patch(
            f"/api/v1/invoices/{invoice_id}/lines/{line_id}/discount",
            headers={"Authorization": f"Bearer {token}"},
            json={"discount_amount": "200.00"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["discount_total"] == 200.0
        assert result["data"]["total"] == 800.0

    async def test_generate_term_invoices_for_student_api(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test generating term invoices for a single student via API."""
        token, user_id, _ = await self._setup_auth_and_data(db_session)

        category = Category(name="Term Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        school_fee_kit = Kit(
            category_id=category.id,
            sku_code="SCHOOL-FEE-TERM",
            name="School Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.BY_GRADE.value,
            price=None,
            requires_full_payment=False,
            is_active=True,
        )
        transport_fee_kit = Kit(
            category_id=category.id,
            sku_code="TRANSPORT-FEE-TERM",
            name="Transport Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.BY_ZONE.value,
            price=None,
            requires_full_payment=False,
            is_active=True,
        )
        admission_fee_kit = Kit(
            category_id=category.id,
            sku_code="ADMISSION-FEE",
            name="Admission Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("5000.00"),
            requires_full_payment=True,
            is_active=True,
        )
        interview_fee_kit = Kit(
            category_id=category.id,
            sku_code="INTERVIEW-FEE",
            name="Interview Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            requires_full_payment=True,
            is_active=True,
        )
        db_session.add(school_fee_kit)
        db_session.add(transport_fee_kit)
        db_session.add(admission_fee_kit)
        db_session.add(interview_fee_kit)
        await db_session.flush()

        grade = Grade(code="TERM", name="Term Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        zone = TransportZone(zone_name="Term Zone", zone_code="TERMZ", is_active=True)
        db_session.add(zone)
        await db_session.flush()

        term = Term(
            year=2026,
            term_number=1,
            display_name="Term 1 2026",
            status=TermStatus.ACTIVE.value,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            created_by_id=user_id,
        )
        db_session.add(term)
        await db_session.flush()

        price_setting = PriceSetting(
            term_id=term.id,
            grade=grade.code,
            school_fee_amount=Decimal("15000.00"),
        )
        db_session.add(price_setting)

        transport_pricing = TransportPricing(
            term_id=term.id,
            zone_id=zone.id,
            transport_fee_amount=Decimal("5000.00"),
        )
        db_session.add(transport_pricing)
        await db_session.flush()

        student = Student(
            student_number="STU-TERM-000001",
            first_name="Term",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            transport_zone_id=zone.id,
            guardian_name="Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user_id,
        )
        db_session.add(student)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/api/v1/invoices/generate-term-invoices/student",
            headers={"Authorization": f"Bearer {token}"},
            json={"term_id": term.id, "student_id": student.id},
        )

        assert response.status_code == 200
        result = response.json()["data"]
        assert result["school_fee_invoices_created"] == 1
        assert result["transport_invoices_created"] == 1
        assert result["total_students_processed"] == 1

        adhoc_result = await db_session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(
                Invoice.term_id == term.id,
                Invoice.student_id == student.id,
                Invoice.invoice_type == InvoiceType.ADHOC.value,
            )
        )
        assert (adhoc_result.scalar() or 0) == 1

"""Tests for Reservations module."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.inventory.schemas import ReceiveStockRequest
from src.modules.inventory.service import InventoryService
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, Item, ItemType, Kit, KitItem, PriceType
from src.modules.reservations.models import ReservationStatus
from src.modules.reservations.service import ReservationService
from src.modules.students.models import Gender, Grade, Student, StudentStatus


class TestReservationService:
    """Tests for ReservationService."""

    async def _setup_test_data(self, db_session: AsyncSession) -> dict:
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="reservation_test@school.com",
            password="Test123!",
            full_name="Reservation Tester",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.flush()

        category = Category(name="Reservation Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        item = Item(
            category_id=category.id,
            sku_code="RES-ITEM-001",
            name="Reservation Item",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            is_active=True,
        )
        db_session.add(item)
        await db_session.flush()

        kit = Kit(
            category_id=category.id,
            sku_code="RES-KIT-001",
            name="Reservation Kit",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            requires_full_payment=True,
            is_active=True,
        )
        db_session.add(kit)
        await db_session.flush()

        kit_item = KitItem(
            kit_id=kit.id,
            item_id=item.id,
            quantity=1,
            source_type="item",
        )
        db_session.add(kit_item)

        grade = Grade(code="RES1", name="Reservation Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-RES-000001",
            first_name="Res",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="Res Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        invoice = Invoice(
            invoice_number="INV-RES-000001",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("1000.00"),
            amount_due=Decimal("0.00"),
            created_by_id=user.id,
        )
        invoice.lines = []
        db_session.add(invoice)
        await db_session.flush()

        line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=kit.id,
            description="Reservation Item",
            quantity=2,
            unit_price=Decimal("500.00"),
            line_total=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("1000.00"),
            paid_amount=Decimal("1000.00"),
            remaining_amount=Decimal("0.00"),
        )
        db_session.add(line)
        invoice.lines.append(line)
        await db_session.flush()

        inventory = InventoryService(db_session)
        await inventory.receive_stock(
            ReceiveStockRequest(
                item_id=item.id,
                quantity=10,
                unit_cost=Decimal("200.00"),
                reference_type="test",
                reference_id=1,
                notes="Initial stock",
            ),
            received_by_id=user.id,
        )

        return {
            "user": user,
            "student": student,
            "invoice": invoice,
            "line": line,
            "item": item,
            "kit": kit,
        }

    async def test_create_reservation_from_paid_line(self, db_session: AsyncSession):
        data = await self._setup_test_data(db_session)
        service = ReservationService(db_session)

        reservation = await service.create_from_line(
            invoice_line_id=data["line"].id,
            created_by_id=data["user"].id,
        )

        assert reservation is not None
        assert reservation.invoice_line_id == data["line"].id
        assert reservation.status == ReservationStatus.PENDING.value
        assert len(reservation.items) == 1
        assert reservation.items[0].quantity_required == 2
        assert reservation.items[0].quantity_reserved == 2

    async def test_issue_and_cancel_reservation(self, db_session: AsyncSession):
        data = await self._setup_test_data(db_session)
        service = ReservationService(db_session)

        reservation = await service.create_from_line(
            invoice_line_id=data["line"].id,
            created_by_id=data["user"].id,
        )

        await service.issue_items(
            reservation_id=reservation.id,
            items=[(reservation.items[0].id, 1)],
            issued_by_id=data["user"].id,
        )

        reservation = await service.get_by_id(reservation.id)
        assert reservation.status == ReservationStatus.PARTIAL.value
        assert reservation.items[0].quantity_issued == 1
        assert reservation.items[0].quantity_reserved == 1

        inventory = InventoryService(db_session)
        stock_before = await inventory.get_stock_by_item_id(data["item"].id)
        on_hand_before = stock_before.quantity_on_hand
        reserved_before = stock_before.quantity_reserved

        await service.cancel_reservation(
            reservation_id=reservation.id,
            cancelled_by_id=data["user"].id,
            reason="Test cancel",
        )

        reservation = await service.get_by_id(reservation.id)
        assert reservation.status == ReservationStatus.CANCELLED.value

        stock_after = await inventory.get_stock_by_item_id(data["item"].id)
        assert stock_after.quantity_on_hand == on_hand_before + 1
        assert stock_after.quantity_reserved == reserved_before - 1

    async def test_reservation_created_on_invoice_issue_before_payment(
        self, db_session: AsyncSession
    ):
        """Test that reservations are created immediately after invoice issue, before payment."""
        data = await self._setup_test_data(db_session)

        # Create a new invoice with unpaid status
        invoice = Invoice(
            invoice_number="INV-RES-000002",
            student_id=data["student"].id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.DRAFT.value,
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("1000.00"),
            created_by_id=data["user"].id,
        )
        invoice.lines = []
        db_session.add(invoice)
        await db_session.flush()

        line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=data["kit"].id,
            description="Reservation Item",
            quantity=2,
            unit_price=Decimal("500.00"),
            line_total=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("1000.00"),
            paid_amount=Decimal("0.00"),  # Not paid yet
            remaining_amount=Decimal("1000.00"),
        )
        db_session.add(line)
        invoice.lines.append(line)
        await db_session.flush()

        # Issue invoice (should create reservation even though unpaid)
        from src.modules.invoices.service import InvoiceService
        invoice_service = InvoiceService(db_session)
        await invoice_service.issue_invoice(invoice.id, issued_by_id=data["user"].id)

        # Sync reservations
        service = ReservationService(db_session)
        await service.sync_for_invoice(invoice.id, user_id=data["user"].id)
        await db_session.commit()

        # Check that reservation was created
        reservation = await service.get_by_invoice_line_id(line.id)
        assert reservation is not None
        assert reservation.invoice_line_id == line.id
        assert reservation.status == ReservationStatus.PENDING.value
        assert len(reservation.items) == 1
        assert reservation.items[0].quantity_required == 2

    async def test_reservation_cancelled_when_invoice_cancelled(
        self, db_session: AsyncSession
    ):
        """Test that reservations are automatically cancelled when invoice is cancelled."""
        data = await self._setup_test_data(db_session)
        
        # Create a new invoice without payment (can be cancelled)
        invoice = Invoice(
            invoice_number="INV-RES-000003",
            student_id=data["student"].id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("0.00"),  # No payment
            amount_due=Decimal("1000.00"),
            created_by_id=data["user"].id,
        )
        invoice.lines = []
        db_session.add(invoice)
        await db_session.flush()

        line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=data["kit"].id,
            description="Reservation Item",
            quantity=2,
            unit_price=Decimal("500.00"),
            line_total=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("1000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("1000.00"),
        )
        db_session.add(line)
        invoice.lines.append(line)
        await db_session.flush()
        await db_session.commit()

        service = ReservationService(db_session)

        # Create reservation
        reservation = await service.create_from_line(
            invoice_line_id=line.id,
            created_by_id=data["user"].id,
        )
        await db_session.commit()

        # Cancel invoice
        from src.modules.invoices.service import InvoiceService
        invoice_service = InvoiceService(db_session)
        await invoice_service.cancel_invoice(invoice.id, cancelled_by_id=data["user"].id)
        
        # Sync reservations (should cancel reservation)
        await service.sync_for_invoice(invoice.id, user_id=data["user"].id)
        await db_session.commit()

        # Check that reservation was cancelled
        reservation = await service.get_by_id(reservation.id)
        assert reservation.status == ReservationStatus.CANCELLED.value

    async def test_issue_reservation_with_zero_quantity_items(
        self, db_session: AsyncSession
    ):
        """Test that items with quantity 0 are skipped when issuing reservation."""
        data = await self._setup_test_data(db_session)
        service = ReservationService(db_session)

        reservation = await service.create_from_line(
            invoice_line_id=data["line"].id,
            created_by_id=data["user"].id,
        )
        await db_session.commit()

        # Try to issue with one item having quantity 0 (should be skipped)
        # First item: quantity 1, second item: quantity 0 (should be skipped)
        reservation_item_id = reservation.items[0].id

        # Issue only 1 out of 2 required
        await service.issue_items(
            reservation_id=reservation.id,
            items=[(reservation_item_id, 1)],
            issued_by_id=data["user"].id,
        )

        reservation = await service.get_by_id(reservation.id)
        assert reservation.status == ReservationStatus.PARTIAL.value
        assert reservation.items[0].quantity_issued == 1
        assert reservation.items[0].quantity_reserved == 1

    async def test_issue_reservation_rejects_all_zero_quantities(
        self, db_session: AsyncSession
    ):
        """Test that issuing with all items having quantity 0 raises error."""
        data = await self._setup_test_data(db_session)
        service = ReservationService(db_session)

        reservation = await service.create_from_line(
            invoice_line_id=data["line"].id,
            created_by_id=data["user"].id,
        )
        await db_session.commit()

        reservation_item_id = reservation.items[0].id

        # Try to issue with quantity 0 (should raise error)
        from src.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="At least one item"):
            await service.issue_items(
                reservation_id=reservation.id,
                items=[(reservation_item_id, 0)],
                issued_by_id=data["user"].id,
            )

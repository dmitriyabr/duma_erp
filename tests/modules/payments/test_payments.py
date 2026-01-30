"""Tests for Payments module."""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.payments.models import Payment, PaymentMethod, PaymentStatus, CreditAllocation
from src.modules.payments.schemas import (
    AllocationCreate,
    AutoAllocateRequest,
    PaymentCreate,
    PaymentFilters,
)
from src.modules.payments.service import PaymentService
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.students.models import Grade, Student, StudentStatus, Gender
from src.modules.items.models import Category, Item, ItemType, Kit, KitItem, PriceType


class TestPaymentService:
    """Tests for PaymentService."""

    async def _setup_test_data(self, db_session: AsyncSession) -> dict:
        """Create test data for payment tests."""
        # Create user first
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="payment_test@school.com",
            password="Test123!",
            full_name="Payment Test User",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.flush()

        # Create category
        category = Category(name="Payment Test Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        # Create kit
        kit = Kit(
            category_id=category.id,
            sku_code="PAY-TEST-KIT",
            name="Payment Test Kit",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(kit)
        await db_session.flush()

        # Create grade
        grade = Grade(code="PAYTST", name="Payment Test Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        # Create student
        student = Student(
            student_number="STU-PAY-000001",
            first_name="Payment",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="Payment Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        # Create invoices for the student
        invoice1 = Invoice(
            invoice_number="INV-PAY-000001",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("5000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("5000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("5000.00"),
            created_by_id=user.id,
        )
        invoice1.lines = []
        db_session.add(invoice1)

        invoice2 = Invoice(
            invoice_number="INV-PAY-000002",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("3000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("3000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("3000.00"),
            created_by_id=user.id,
        )
        invoice2.lines = []
        db_session.add(invoice2)

        invoice3 = Invoice(
            invoice_number="INV-PAY-000003",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("2000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("2000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("2000.00"),
            created_by_id=user.id,
        )
        invoice3.lines = []
        db_session.add(invoice3)

        await db_session.flush()

        # Add lines to invoices
        line1 = InvoiceLine(
            invoice_id=invoice1.id,
            kit_id=kit.id,
            description="Test Item",
            quantity=5,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("5000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("5000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("5000.00"),
        )
        db_session.add(line1)
        invoice1.lines.append(line1)

        line2 = InvoiceLine(
            invoice_id=invoice2.id,
            kit_id=kit.id,
            description="Test Item",
            quantity=3,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("3000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("3000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("3000.00"),
        )
        db_session.add(line2)
        invoice2.lines.append(line2)

        line3 = InvoiceLine(
            invoice_id=invoice3.id,
            kit_id=kit.id,
            description="Test Item",
            quantity=2,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("2000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("2000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("2000.00"),
        )
        db_session.add(line3)
        invoice3.lines.append(line3)

        await db_session.commit()

        return {
            "user": user,
            "student": student,
            "invoice1": invoice1,  # 5000
            "invoice2": invoice2,  # 3000
            "invoice3": invoice3,  # 2000
            "kit": kit,
        }

    async def test_create_payment(self, db_session: AsyncSession):
        """Test creating a payment."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="MPESA123456",
            ),
            received_by_id=data["user"].id,
        )

        assert payment.id is not None
        assert payment.payment_number.startswith("PAY-")
        assert payment.amount == Decimal("5000.00")
        assert payment.status == PaymentStatus.PENDING.value
        assert payment.receipt_number is None

    async def test_complete_payment(self, db_session: AsyncSession):
        """Test completing a payment generates receipt number."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_date=date.today(),
                reference="BANK-REF-123",
            ),
            received_by_id=data["user"].id,
        )

        completed = await service.complete_payment(payment.id, data["user"].id)

        assert completed.status == PaymentStatus.COMPLETED.value
        assert completed.receipt_number is not None
        assert completed.receipt_number.startswith("RCP-")

    async def test_cancel_payment(self, db_session: AsyncSession):
        """Test cancelling a pending payment."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )

        cancelled = await service.cancel_payment(payment.id, data["user"].id, "Test cancel")

        assert cancelled.status == PaymentStatus.CANCELLED.value

    async def test_get_student_balance(self, db_session: AsyncSession):
        """Test getting student credit balance."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        # Initially no balance
        balance = await service.get_student_balance(data["student"].id)
        assert balance.available_balance == Decimal("0.00")

        # Create and complete a payment (triggers auto-allocation)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("10000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        # Auto-allocation runs on complete: 10000 distributed across 3 invoices
        balance = await service.get_student_balance(data["student"].id)
        assert balance.total_payments == Decimal("10000.00")
        assert balance.total_allocated == Decimal("10000.00")
        assert balance.available_balance == Decimal("0.00")

    async def test_manual_allocation(self, db_session: AsyncSession):
        """Test manual credit allocation to invoice."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        # Create and complete payment (auto-allocates everything)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("10000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        # Undo auto-allocations so we have balance for manual test
        alloc_result = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        for alloc in alloc_result.scalars().all():
            await service.delete_allocation(alloc.id, data["user"].id, "Test undo")

        # Allocate to invoice1 (5000)
        allocation = await service.allocate_manual(
            AllocationCreate(
                student_id=data["student"].id,
                invoice_id=data["invoice1"].id,
                amount=Decimal("5000.00"),
            ),
            allocated_by_id=data["user"].id,
        )

        assert allocation.amount == Decimal("5000.00")

        # Check balance reduced
        balance = await service.get_student_balance(data["student"].id)
        assert balance.available_balance == Decimal("5000.00")

    async def test_auto_allocation_proportional(self, db_session: AsyncSession):
        """Test auto allocation distributes proportionally across partial_ok invoices."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        # Create and complete payment for 6000 (triggers auto-allocate proportionally)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("6000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        # complete_payment already ran allocate_auto; balance should be 0
        balance = await service.get_student_balance(data["student"].id)
        assert balance.available_balance == Decimal("0.00")
        assert balance.total_allocated == Decimal("6000.00")

        # Proportional: 5000:3000:2000 = 50%:30%:20% of 6000 -> 3000, 1800, 1200
        from src.modules.invoices.models import Invoice

        inv_result = await db_session.execute(
            select(Invoice)
            .where(Invoice.student_id == data["student"].id)
            .order_by(Invoice.invoice_number)
        )
        invoices = list(inv_result.scalars().all())
        paid_totals = sorted([inv.paid_total for inv in invoices], reverse=True)
        assert paid_totals[0] == Decimal("3000.00")
        assert paid_totals[1] == Decimal("1800.00")
        assert paid_totals[2] == Decimal("1200.00")

    async def test_auto_allocation_max_amount(self, db_session: AsyncSession):
        """Test auto allocation with max_amount limit."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        # Create and complete payment for 10000 (auto-allocates all)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("10000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        # Undo auto-allocations to get balance back
        alloc_result = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        for alloc in alloc_result.scalars().all():
            await service.delete_allocation(alloc.id, data["user"].id, "Test undo")

        # Use a fresh session so allocate_auto sees updated invoice amount_due
        from tests.conftest import test_async_session

        async with test_async_session() as new_session:
            service2 = PaymentService(new_session)
            result = await service2.allocate_auto(
                AutoAllocateRequest(
                    student_id=data["student"].id,
                    max_amount=Decimal("3000.00"),
                ),
                allocated_by_id=data["user"].id,
            )

        assert result.total_allocated == Decimal("3000.00")
        assert result.remaining_balance == Decimal("7000.00")

    async def test_auto_allocation_requires_full_payment(self, db_session: AsyncSession):
        """Test requires_full invoices get priority but can receive partial payment."""
        # Setup: create user, grade, student
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="fullpay_test@school.com",
            password="Test123!",
            full_name="Full Pay Test User",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.flush()

        category = Category(name="Full Pay Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        # Create inventory item for product kit
        product_item = Item(
            category_id=category.id,
            sku_code="FULLPAY-PRODUCT-ITEM",
            name="Product Item",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=True,
            is_active=True,
        )
        db_session.add(product_item)
        await db_session.flush()

        product_kit = Kit(
            category_id=category.id,
            sku_code="FULLPAY-PRODUCT",
            name="Product Kit",
            item_type=ItemType.PRODUCT.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=True,
            is_active=True,
        )
        db_session.add(product_kit)
        await db_session.flush()

        db_session.add(
            KitItem(
                kit_id=product_kit.id,
                item_id=product_item.id,
                quantity=1,
            )
        )

        # Create a SERVICE kit that can be paid partially
        service_kit = Kit(
            category_id=category.id,
            sku_code="FULLPAY-SERVICE",
            name="Service Kit",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(service_kit)
        await db_session.flush()

        grade = Grade(code="FULLPY", name="Full Pay Grade", display_order=99, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-FULLPAY-001",
            first_name="FullPay",
            last_name="Student",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()

        # Create invoice with PRODUCT (requires full payment) - amount 3000
        invoice_product = Invoice(
            invoice_number="INV-FULLPAY-PROD",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("3000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("3000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("3000.00"),
            created_by_id=user.id,
        )
        db_session.add(invoice_product)
        await db_session.flush()

        line_product = InvoiceLine(
            invoice_id=invoice_product.id,
            kit_id=product_kit.id,
            description="Product",
            quantity=3,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("3000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("3000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("3000.00"),
        )
        db_session.add(line_product)

        # Create invoice with SERVICE (can be paid partially) - amount 5000
        invoice_service = Invoice(
            invoice_number="INV-FULLPAY-SVC",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("5000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("5000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("5000.00"),
            created_by_id=user.id,
        )
        db_session.add(invoice_service)
        await db_session.flush()

        line_service = InvoiceLine(
            invoice_id=invoice_service.id,
            kit_id=service_kit.id,
            description="Service",
            quantity=5,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("5000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("5000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("5000.00"),
        )
        db_session.add(line_service)

        await db_session.commit()

        # Verify requires_full_payment is set correctly by reloading from DB
        result = await db_session.execute(
            select(Invoice)
            .where(Invoice.student_id == student.id)
            .options(
                selectinload(Invoice.lines).selectinload(InvoiceLine.kit),
            )
        )
        loaded_invoices = list(result.scalars().all())

        # Find which is which
        prod_inv = next(i for i in loaded_invoices if i.invoice_number == "INV-FULLPAY-PROD")
        svc_inv = next(i for i in loaded_invoices if i.invoice_number == "INV-FULLPAY-SVC")

        # Verify the property works
        assert prod_inv.requires_full_payment == True, "Product invoice should require full payment"
        assert svc_inv.requires_full_payment == False, "Service invoice should allow partial payment"

        # Now test allocation with balance of 2000
        # - Product invoice (3000): can't pay fully with 2000, SKIP
        # - Service invoice (5000): can pay partially with 2000
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=student.id,
                amount=Decimal("2000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=user.id,
        )
        await service.complete_payment(payment.id, user.id)

        # complete_payment already ran allocate_auto: requires_full (product) first
        # gets partial 2000; service gets 0
        result = await service.allocate_auto(
            AutoAllocateRequest(student_id=student.id),
            allocated_by_id=user.id,
        )

        # Second call: no balance left (already allocated on complete)
        assert result.total_allocated == Decimal("0.00")
        assert result.remaining_balance == Decimal("0.00")

        # After first (on complete): product invoice got 2000 partial, service 0
        inv_result = await db_session.execute(
            select(Invoice)
            .where(Invoice.student_id == student.id)
            .options(selectinload(Invoice.lines))
        )
        invs = list(inv_result.scalars().all())
        prod_inv = next(i for i in invs if i.invoice_number == "INV-FULLPAY-PROD")
        assert prod_inv.paid_total == Decimal("2000.00")
        svc_inv = next(i for i in invs if i.invoice_number == "INV-FULLPAY-SVC")
        assert svc_inv.paid_total == Decimal("0.00")

    async def test_delete_allocation(self, db_session: AsyncSession):
        """Test deleting an allocation returns credit to balance."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        # Create and complete payment (auto-allocates proportionally)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        # Get one of the auto-allocations and delete it
        alloc_result = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        allocations = list(alloc_result.scalars().all())
        assert len(allocations) >= 1
        allocation_to_delete = allocations[0]
        amount_deleted = allocation_to_delete.amount

        balance_before = await service.get_student_balance(data["student"].id)
        assert balance_before.available_balance == Decimal("0.00")

        await service.delete_allocation(
            allocation_to_delete.id, data["user"].id, "Test delete"
        )

        balance_after = await service.get_student_balance(data["student"].id)
        assert balance_after.available_balance == amount_deleted

    async def test_get_statement(self, db_session: AsyncSession):
        """Test generating account statement."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        # Create and complete payment (auto-allocates all)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("10000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="test-ref",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        # Undo auto-allocations so we can manually allocate 2000 for statement test
        alloc_result = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        for alloc in alloc_result.scalars().all():
            await service.delete_allocation(alloc.id, data["user"].id, "Test undo")

        allocation = await service.allocate_manual(
            AllocationCreate(
                student_id=data["student"].id,
                invoice_id=data["invoice3"].id,
                amount=Decimal("2000.00"),
            ),
            allocated_by_id=data["user"].id,
        )
        allocation.created_at = datetime.now(timezone.utc)
        await db_session.commit()

        statement = await service.get_statement(
            data["student"].id,
            date.today() - timedelta(days=1),
            date.today() + timedelta(days=1),
        )

        assert statement.student_id == data["student"].id
        assert statement.total_credits == Decimal("10000.00")
        assert statement.total_debits == Decimal("2000.00")
        assert statement.closing_balance == Decimal("8000.00")
        assert len(statement.entries) == 2  # 1 payment + 1 allocation


class TestPaymentEndpoints:
    """Tests for payment API endpoints."""

    async def _setup_auth_and_data(
        self, db_session: AsyncSession
    ) -> tuple[str, int, dict]:
        """Create super admin and test data."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="payment_api@school.com",
            password="SuperAdmin123",
            full_name="Payment API Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        _, access_token, _ = await auth_service.authenticate(
            "payment_api@school.com", "SuperAdmin123"
        )

        # Create grade
        grade = Grade(code="PAYAPI", name="Payment API Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        # Create student
        student = Student(
            student_number="STU-PAYAPI-001",
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

        # Create invoice
        invoice = Invoice(
            invoice_number="INV-PAYAPI-001",
            student_id=student.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("5000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("5000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("5000.00"),
            created_by_id=user.id,
        )
        invoice.lines = []
        db_session.add(invoice)
        await db_session.commit()

        return access_token, user.id, {"student": student, "invoice": invoice}

    async def test_create_payment_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a payment via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "5000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "reference": "MPESA-API-123",
            },
        )

        assert response.status_code == 201
        result = response.json()
        assert result["success"] is True
        assert result["data"]["payment_number"].startswith("PAY-")
        assert result["data"]["status"] == "pending"

    async def test_complete_payment_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test completing a payment via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        # Create payment
        create_response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "5000.00",
                "payment_method": "bank_transfer",
                "payment_date": str(date.today()),
                "reference": "test-ref",
            },
        )
        payment_id = create_response.json()["data"]["id"]

        # Complete payment
        response = await client.post(
            f"/api/v1/payments/{payment_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["status"] == "completed"
        assert result["data"]["receipt_number"] is not None

    async def test_get_balance_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting student balance via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        response = await client.get(
            f"/api/v1/payments/students/{data['student'].id}/balance",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["student_id"] == data["student"].id
        assert Decimal(result["data"]["available_balance"]) == Decimal("0.00")

    async def test_auto_allocate_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test auto allocation: complete runs it; second call is no-op when nothing left."""
        token, _, data = await self._setup_auth_and_data(db_session)

        # Create and complete payment (backend runs allocate_auto; invoice 5000 fully paid)
        create_response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "10000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "reference": "test-ref",
            },
        )
        payment_id = create_response.json()["data"]["id"]

        await client.post(
            f"/api/v1/payments/{payment_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Balance: 10000 - 5000 (allocated to invoice) = 5000
        balance_response = await client.get(
            f"/api/v1/payments/students/{data['student'].id}/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert balance_response.status_code == 200
        assert Decimal(balance_response.json()["data"]["available_balance"]) == Decimal(
            "5000.00"
        )

        # Second auto-allocate: no unpaid invoices (single invoice already fully paid)
        response = await client.post(
            "/api/v1/payments/allocations/auto",
            headers={"Authorization": f"Bearer {token}"},
            json={"student_id": data["student"].id},
        )
        assert response.status_code == 200
        result = response.json()
        assert Decimal(result["data"]["total_allocated"]) == Decimal("0.00")
        assert result["data"]["invoices_fully_paid"] == 0

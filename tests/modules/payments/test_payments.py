"""Tests for Payments module."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.payments.models import (
    CreditAllocation,
    CreditAllocationReversal,
    PaymentMethod,
    PaymentRefundSource,
    PaymentStatus,
)
from src.modules.payments.schemas import (
    AllocationCreate,
    AutoAllocateRequest,
    BillingAccountRefundCreate,
    BillingAccountRefundPreviewRequest,
    PaymentCreate,
    PaymentFilters,
    PaymentRefundCreate,
)
from src.modules.payments.service import PaymentService
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.students.models import Grade, Student, StudentStatus, Gender
from src.modules.items.models import Category, Item, ItemType, Kit, KitItem, PriceType
from src.modules.terms.models import Term, TermStatus


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

    async def test_complete_payment_prefers_selected_invoice_before_auto_allocate(
        self, db_session: AsyncSession
    ):
        """Preferred invoice should receive this payment before older/smaller debts."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                preferred_invoice_id=data["invoice1"].id,
                amount=Decimal("2000.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_date=date.today(),
                reference="BANK-PREFERRED-2000",
            ),
            received_by_id=data["user"].id,
        )

        await service.complete_payment(payment.id, data["user"].id)

        allocations_result = await db_session.execute(
            select(CreditAllocation)
            .where(CreditAllocation.student_id == data["student"].id)
            .order_by(CreditAllocation.id.asc())
        )
        allocations = list(allocations_result.scalars().all())
        assert len(allocations) == 1
        assert allocations[0].invoice_id == data["invoice1"].id
        assert allocations[0].amount == Decimal("2000.00")

        invoice1 = await db_session.get(Invoice, data["invoice1"].id)
        invoice3 = await db_session.get(Invoice, data["invoice3"].id)
        assert invoice1 is not None
        assert invoice3 is not None
        assert invoice1.amount_due == Decimal("3000.00")
        assert invoice3.amount_due == Decimal("2000.00")

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

    async def test_partial_refund_releases_allocations_and_reopens_invoice(
        self, db_session: AsyncSession
    ):
        """Refund should reverse current allocations before reducing account capital."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("6000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="refund-partial-test",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        refund = await service.refund_payment(
            payment.id,
            PaymentRefundCreate(
                amount=Decimal("1000.00"),
                refund_date=date.today(),
                refund_method="mpesa",
                reference_number="RFND-PARTIAL-001",
                proof_text="M-Pesa refund confirmation",
                reason="Parent requested refund",
            ),
            refunded_by_id=data["user"].id,
        )

        assert refund.amount == Decimal("1000.00")
        assert refund.refund_method == "mpesa"
        assert refund.reference_number == "RFND-PARTIAL-001"
        assert refund.proof_text == "M-Pesa refund confirmation"

        balance = await service.get_student_balance(data["student"].id)
        assert balance.total_payments == Decimal("6000.00")
        assert balance.total_refunded == Decimal("1000.00")
        assert balance.total_allocated == Decimal("5000.00")
        assert balance.available_balance == Decimal("0.00")

        invoice3 = await db_session.get(Invoice, data["invoice3"].id)
        assert invoice3 is not None
        assert invoice3.status == InvoiceStatus.PARTIALLY_PAID.value
        assert invoice3.paid_total == Decimal("200.00")
        assert invoice3.amount_due == Decimal("1800.00")

        refreshed_payment = await service.get_payment_by_id(payment.id)
        assert sum((item.amount for item in refreshed_payment.refunds), Decimal("0.00")) == Decimal(
            "1000.00"
        )

    async def test_full_refund_clears_allocations_and_zeroes_refundable_amount(
        self, db_session: AsyncSession
    ):
        """Full refund should remove all allocations funded by the account capital."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("6000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="refund-full-test",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        await service.refund_payment(
            payment.id,
            PaymentRefundCreate(
                amount=Decimal("6000.00"),
                refund_date=date.today(),
                reference_number="RFND-FULL-001",
                reason="Payment fully reversed",
            ),
            refunded_by_id=data["user"].id,
        )

        balance = await service.get_student_balance(data["student"].id)
        assert balance.total_payments == Decimal("6000.00")
        assert balance.total_refunded == Decimal("6000.00")
        assert balance.total_allocated == Decimal("0.00")
        assert balance.available_balance == Decimal("0.00")

        allocations_result = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.billing_account_id == balance.billing_account_id
            )
        )
        allocations = list(allocations_result.scalars().all())
        assert allocations
        assert all(allocation.amount == Decimal("0.00") for allocation in allocations)

        invoices_result = await db_session.execute(
            select(Invoice).where(Invoice.student_id == data["student"].id)
        )
        invoices = list(invoices_result.scalars().all())
        assert all(invoice.status == InvoiceStatus.ISSUED.value for invoice in invoices)
        assert all(invoice.paid_total == Decimal("0.00") for invoice in invoices)

        refreshed_payment = await service.get_payment_by_id(payment.id)
        assert sum((item.amount for item in refreshed_payment.refunds), Decimal("0.00")) == Decimal(
            "6000.00"
        )

    async def test_account_refund_uses_free_credit_without_reopening_invoices(
        self, db_session: AsyncSession
    ):
        """Account-level refund should consume free account credit before allocations."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("12000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="account-refund-free-credit",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)
        balance_before = await service.get_student_balance(data["student"].id)
        assert balance_before.available_balance == Decimal("2000.00")

        preview = await service.preview_billing_account_refund(
            balance_before.billing_account_id,
            BillingAccountRefundPreviewRequest(
                amount=Decimal("1500.00"),
                refund_date=date.today(),
            ),
        )
        assert preview.amount_to_reopen == Decimal("0.00")
        assert preview.allocation_reversals == []
        assert preview.payment_sources[0].source_amount == Decimal("1500.00")

        refund = await service.create_billing_account_refund(
            balance_before.billing_account_id,
            BillingAccountRefundCreate(
                amount=Decimal("1500.00"),
                refund_date=date.today(),
                refund_method="mpesa",
                reference_number="RFND-ACCOUNT-FREE",
                reason="Parent requested account refund",
            ),
            refunded_by_id=data["user"].id,
        )

        assert refund.payment_id is None
        assert refund.refund_number.startswith("RFND-")
        assert refund.sources[0].payment_id == payment.id
        assert refund.sources[0].amount == Decimal("1500.00")
        assert refund.allocation_reversals == []

        balance_after = await service.get_student_balance(data["student"].id)
        assert balance_after.total_refunded == Decimal("1500.00")
        assert balance_after.available_balance == Decimal("500.00")
        assert balance_after.total_allocated == Decimal("10000.00")

    async def test_account_refund_can_span_payments_and_link_reversals(
        self, db_session: AsyncSession
    ):
        """One account refund can consume several payment sources and reopen allocations."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        older = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("4000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today() - timedelta(days=1),
                reference="account-refund-source-older",
            ),
            received_by_id=data["user"].id,
        )
        newer = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("3000.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_date=date.today(),
                reference="account-refund-source-newer",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(older.id, data["user"].id)
        await service.complete_payment(newer.id, data["user"].id)

        balance = await service.get_student_balance(data["student"].id)
        preview = await service.preview_billing_account_refund(
            balance.billing_account_id,
            BillingAccountRefundPreviewRequest(
                amount=Decimal("5500.00"),
                refund_date=date.today(),
            ),
        )

        assert preview.amount_to_reopen == Decimal("5500.00")
        assert [source.payment_id for source in preview.payment_sources] == [newer.id, older.id]
        assert [source.source_amount for source in preview.payment_sources] == [
            Decimal("3000.00"),
            Decimal("2500.00"),
        ]
        assert sum(
            (impact.reversal_amount for impact in preview.allocation_reversals),
            Decimal("0.00"),
        ) == Decimal("5500.00")

        refund = await service.create_billing_account_refund(
            balance.billing_account_id,
            BillingAccountRefundCreate(
                amount=Decimal("5500.00"),
                refund_date=date.today(),
                refund_method="bank_transfer",
                reference_number="RFND-ACCOUNT-SPAN",
                reason="Parent requested one account refund",
            ),
            refunded_by_id=data["user"].id,
        )

        sources_result = await db_session.execute(
            select(PaymentRefundSource).where(PaymentRefundSource.refund_id == refund.id)
        )
        sources = list(sources_result.scalars().all())
        assert [(source.payment_id, source.amount) for source in sources] == [
            (newer.id, Decimal("3000.00")),
            (older.id, Decimal("2500.00")),
        ]

        reversals_result = await db_session.execute(
            select(CreditAllocationReversal).where(
                CreditAllocationReversal.refund_id == refund.id
            )
        )
        reversals = list(reversals_result.scalars().all())
        assert sum((reversal.amount for reversal in reversals), Decimal("0.00")) == Decimal(
            "5500.00"
        )

        balance_after = await service.get_student_balance(data["student"].id)
        assert balance_after.total_refunded == Decimal("5500.00")
        assert balance_after.total_allocated == Decimal("1500.00")
        assert balance_after.available_balance == Decimal("0.00")

    async def test_list_payments_orders_by_payment_date_desc(
        self, db_session: AsyncSession
    ):
        """Payments list should show the most recent payment_date first."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        newer = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("1000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date(2026, 1, 15),
                reference="newer-date",
            ),
            received_by_id=data["user"].id,
        )
        older = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("1000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date(2026, 1, 10),
                reference="older-date",
            ),
            received_by_id=data["user"].id,
        )

        payments, total = await service.list_payments(
            PaymentFilters(student_id=data["student"].id, page=1, limit=10)
        )

        assert total == 2
        assert [payment.id for payment in payments] == [newer.id, older.id]

    async def test_list_payments_can_search_by_student_number(
        self, db_session: AsyncSession
    ):
        """Payments list should support searching by student number."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("1500.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date(2026, 1, 12),
                reference="search-student-number",
            ),
            received_by_id=data["user"].id,
        )

        payments, total = await service.list_payments(
            PaymentFilters(search="STU-PAY-000001", page=1, limit=10)
        )

        assert total == 1
        assert [row.id for row in payments] == [payment.id]
        assert payments[0].student.student_number == "STU-PAY-000001"

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

    async def test_update_invoice_paid_amounts_rebuilds_from_line_net_when_header_total_is_stale(
        self, db_session: AsyncSession
    ):
        """Allocation sync must use line net totals, not stale invoice header total."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        invoice_result = await db_session.execute(
            select(Invoice)
            .where(Invoice.id == data["invoice1"].id)
            .options(selectinload(Invoice.lines))
        )
        invoice = invoice_result.scalar_one()
        line = invoice.lines[0]

        # Simulate historical bad data: discount exists on line, but invoice header still says gross total.
        line.discount_amount = Decimal("1000.00")
        line.net_amount = Decimal("4000.00")
        line.remaining_amount = Decimal("4000.00")
        invoice.discount_total = Decimal("0.00")
        invoice.total = Decimal("5000.00")
        invoice.amount_due = Decimal("5000.00")

        db_session.add(
            CreditAllocation(
                student_id=data["student"].id,
                invoice_id=invoice.id,
                invoice_line_id=None,
                amount=Decimal("3000.00"),
                allocated_by_id=data["user"].id,
            )
        )
        await db_session.flush()

        await service._update_invoice_paid_amounts(invoice)

        assert invoice.discount_total == Decimal("1000.00")
        assert invoice.total == Decimal("4000.00")
        assert invoice.paid_total == Decimal("3000.00")
        assert invoice.amount_due == Decimal("1000.00")
        assert line.paid_amount == Decimal("3000.00")
        assert line.remaining_amount == Decimal("1000.00")

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

    async def test_auto_allocation_closes_previous_term_before_active_term(
        self, db_session: AsyncSession
    ):
        """Previous term debt should be fully considered before active-term invoices."""
        data = await self._setup_test_data(db_session)
        user = data["user"]
        previous_term = Term(
            year=2097,
            term_number=1,
            display_name="2097-T1",
            status=TermStatus.CLOSED.value,
            start_date=date(2097, 1, 1),
            end_date=date(2097, 3, 31),
            created_by_id=user.id,
        )
        active_term = Term(
            year=2097,
            term_number=2,
            display_name="2097-T2",
            status=TermStatus.ACTIVE.value,
            start_date=date(2097, 4, 1),
            end_date=date(2097, 6, 30),
            created_by_id=user.id,
        )
        db_session.add_all([previous_term, active_term])
        await db_session.flush()

        data["invoice1"].term_id = active_term.id
        data["invoice2"].term_id = previous_term.id
        data["invoice3"].term_id = active_term.id
        await db_session.commit()

        service = PaymentService(db_session)
        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("4000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="previous-term-first",
            ),
            received_by_id=user.id,
        )
        await service.complete_payment(payment.id, user.id)

        previous_invoice = await db_session.get(Invoice, data["invoice2"].id)
        active_invoice = await db_session.get(Invoice, data["invoice1"].id)

        assert previous_invoice is not None
        assert active_invoice is not None
        assert previous_invoice.paid_total == Decimal("3000.00")
        assert previous_invoice.amount_due == Decimal("0.00")
        assert active_invoice.paid_total > Decimal("0.00")
        assert active_invoice.paid_total < active_invoice.total

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
                source_type="item",
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

    async def test_undo_and_reallocate_preserves_allocation_report_date(
        self, db_session: AsyncSession
    ):
        """Undo + reallocate should not move allocation-based reports to today."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date(2026, 1, 10),
                reference="test-reallocate-date",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)

        alloc_result = await db_session.execute(
            select(CreditAllocation)
            .where(CreditAllocation.student_id == data["student"].id)
            .order_by(CreditAllocation.id.asc())
        )
        allocation_to_reallocate = list(alloc_result.scalars().all())[0]
        original_allocation_id = allocation_to_reallocate.id
        original_amount = allocation_to_reallocate.amount
        original_created_at = datetime(2026, 1, 10, 9, 30, tzinfo=timezone.utc)
        allocation_to_reallocate.created_at = original_created_at
        await db_session.commit()

        result = await service.undo_and_reallocate_allocation(
            original_allocation_id,
            data["user"].id,
            "Test undo and reallocate",
        )

        assert result.total_allocated == original_amount

        refreshed_allocations = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        allocations = list(refreshed_allocations.scalars().all())
        assert all(allocation.id != original_allocation_id for allocation in allocations)

        reallocated_same_day_total = sum(
            (
                allocation.amount
                for allocation in allocations
                if allocation.created_at.date() == original_created_at.date()
            ),
            Decimal("0.00"),
        )
        assert reallocated_same_day_total == original_amount

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
        payment_entry = next(entry for entry in statement.entries if entry.entry_type == "payment")
        allocation_entry = next(
            entry for entry in statement.entries if entry.entry_type == "allocation"
        )
        assert payment_entry.payment_id == payment.id
        assert allocation_entry.allocation_id == allocation.id
        assert allocation_entry.invoice_id == data["invoice3"].id

    async def test_get_statement_includes_refund_entries(self, db_session: AsyncSession):
        """Statement should include refund rows as debits."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("6000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="statement-refund-test",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)
        await service.refund_payment(
            payment.id,
            PaymentRefundCreate(
                amount=Decimal("1000.00"),
                refund_date=date.today(),
                reference_number="RFND-STATEMENT-001",
                reason="Statement refund check",
            ),
            refunded_by_id=data["user"].id,
        )

        statement = await service.get_statement(
            data["student"].id,
            date.today() - timedelta(days=1),
            date.today() + timedelta(days=1),
        )

        assert statement.total_credits == Decimal("7000.00")
        assert statement.total_debits == Decimal("7000.00")
        assert statement.closing_balance == Decimal("0.00")
        refund_entry = next(entry for entry in statement.entries if entry.entry_type == "refund")
        reversal_entry = next(
            entry
            for entry in statement.entries
            if entry.entry_type == "allocation_reversal"
        )
        assert refund_entry.payment_id == payment.id
        assert refund_entry.refund_id is not None
        assert refund_entry.debit == Decimal("1000.00")
        assert reversal_entry.credit == Decimal("1000.00")

    async def test_get_statement_preserves_original_allocation_before_refund(
        self, db_session: AsyncSession
    ):
        """Historical statement should keep the original allocation amount before a later refund."""
        data = await self._setup_test_data(db_session)
        service = PaymentService(db_session)
        payment_date = date.today()
        refund_date = date.today() + timedelta(days=1)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=payment_date,
                reference="statement-historical-refund",
            ),
            received_by_id=data["user"].id,
        )
        await service.complete_payment(payment.id, data["user"].id)
        await service.refund_payment(
            payment.id,
            PaymentRefundCreate(
                amount=Decimal("1000.00"),
                refund_date=refund_date,
                reference_number="RFND-STATEMENT-002",
                reason="Historical statement refund",
            ),
            refunded_by_id=data["user"].id,
        )

        statement = await service.get_statement(
            data["student"].id,
            payment_date,
            payment_date,
        )

        allocation_entries = [
            entry for entry in statement.entries if entry.entry_type == "allocation"
        ]
        assert allocation_entries
        assert sum((entry.debit or Decimal("0.00") for entry in allocation_entries), Decimal("0.00")) == Decimal("5000.00")
        assert statement.total_credits == Decimal("5000.00")
        assert statement.total_debits == Decimal("5000.00")
        assert statement.closing_balance == Decimal("0.00")


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

    async def test_refund_payment_api(self, client: AsyncClient, db_session: AsyncSession):
        """Refund endpoint should reopen paid invoice value and update payment aggregates."""
        token, _, data = await self._setup_auth_and_data(db_session)

        create_response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "5000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "reference": "refund-api-test",
            },
        )
        payment_id = create_response.json()["data"]["id"]

        await client.post(
            f"/api/v1/payments/{payment_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.post(
            f"/api/v1/payments/{payment_id}/refunds",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": "2000.00",
                "refund_date": str(date.today()),
                "refund_method": "mpesa",
                "reference_number": "RFND-API-001",
                "reason": "API refund test",
            },
        )

        assert response.status_code == 201
        result = response.json()
        assert Decimal(result["data"]["amount"]) == Decimal("2000.00")
        assert result["data"]["refund_method"] == "mpesa"
        assert result["data"]["reference_number"] == "RFND-API-001"

        payment_response = await client.get(
            f"/api/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert payment_response.status_code == 200
        payment_data = payment_response.json()["data"]
        assert Decimal(payment_data["refunded_amount"]) == Decimal("2000.00")
        assert Decimal(payment_data["refundable_amount"]) == Decimal("3000.00")
        assert payment_data["refund_status"] == "partial"

        balance_response = await client.get(
            f"/api/v1/payments/students/{data['student'].id}/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert balance_response.status_code == 200
        balance_data = balance_response.json()["data"]
        assert Decimal(balance_data["total_refunded"]) == Decimal("2000.00")
        assert Decimal(balance_data["available_balance"]) == Decimal("0.00")
        assert payment_data["receipt_number"] is not None

    async def test_account_refund_api_preview_create_and_list(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Billing account refund endpoints should preview, create and list one refund document."""
        token, _, data = await self._setup_auth_and_data(db_session)

        create_response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "7000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "reference": "account-refund-api-payment",
            },
        )
        payment_id = create_response.json()["data"]["id"]
        await client.post(
            f"/api/v1/payments/{payment_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )
        balance_response = await client.get(
            f"/api/v1/payments/students/{data['student'].id}/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        account_id = balance_response.json()["data"]["billing_account_id"]

        preview_response = await client.post(
            f"/api/v1/billing-accounts/{account_id}/refunds/preview",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": "2500.00",
                "refund_date": str(date.today()),
            },
        )
        assert preview_response.status_code == 200
        preview = preview_response.json()["data"]
        assert Decimal(preview["amount_to_reopen"]) == Decimal("500.00")
        assert Decimal(preview["payment_sources"][0]["source_amount"]) == Decimal("2500.00")

        create_refund_response = await client.post(
            f"/api/v1/billing-accounts/{account_id}/refunds",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": "2500.00",
                "refund_date": str(date.today()),
                "refund_method": "mpesa",
                "reference_number": "RFND-ACCOUNT-API",
                "reason": "Account refund API test",
            },
        )
        assert create_refund_response.status_code == 201
        refund = create_refund_response.json()["data"]
        assert refund["refund_number"].startswith("RFND-")
        assert refund["payment_id"] is None
        assert Decimal(refund["amount"]) == Decimal("2500.00")
        assert Decimal(refund["payment_sources"][0]["amount"]) == Decimal("2500.00")
        assert Decimal(refund["allocation_reversals"][0]["reversal_amount"]) == Decimal("500.00")

        list_response = await client.get(
            f"/api/v1/billing-accounts/{account_id}/refunds",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        rows = list_response.json()["data"]
        assert len(rows) == 1
        assert rows[0]["refund_number"] == refund["refund_number"]

    async def test_account_refund_api_allows_manual_invoice_allocation_selection(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Manual account refunds should let users choose which invoice allocation is reopened."""
        token, user_id, data = await self._setup_auth_and_data(db_session)

        second_invoice = Invoice(
            invoice_number="INV-PAYAPI-002",
            student_id=data["student"].id,
            invoice_type=InvoiceType.TRANSPORT.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=15),
            subtotal=Decimal("3000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("3000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("3000.00"),
            created_by_id=user_id,
        )
        db_session.add(second_invoice)
        await db_session.commit()

        create_response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "9000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "reference": "account-refund-manual-payment",
            },
        )
        payment_id = create_response.json()["data"]["id"]
        await client.post(
            f"/api/v1/payments/{payment_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )
        balance_response = await client.get(
            f"/api/v1/payments/students/{data['student'].id}/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        account_id = balance_response.json()["data"]["billing_account_id"]

        options_response = await client.get(
            f"/api/v1/billing-accounts/{account_id}/refunds/allocation-options",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert options_response.status_code == 200
        options = options_response.json()["data"]
        selected_option = next(
            option for option in options if option["invoice_number"] == "INV-PAYAPI-002"
        )
        assert selected_option["student_name"] == data["student"].full_name
        assert selected_option["invoice_type"] == InvoiceType.TRANSPORT.value

        manual_reversals = [
            {
                "allocation_id": selected_option["allocation_id"],
                "amount": "1000.00",
            }
        ]
        preview_response = await client.post(
            f"/api/v1/billing-accounts/{account_id}/refunds/preview",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": "2000.00",
                "refund_date": str(date.today()),
                "allocation_reversals": manual_reversals,
            },
        )
        assert preview_response.status_code == 200
        preview = preview_response.json()["data"]
        assert Decimal(preview["amount_to_reopen"]) == Decimal("1000.00")
        assert preview["allocation_reversals"][0]["invoice_number"] == "INV-PAYAPI-002"
        assert preview["allocation_reversals"][0]["invoice_type"] == InvoiceType.TRANSPORT.value

        create_refund_response = await client.post(
            f"/api/v1/billing-accounts/{account_id}/refunds",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": "2000.00",
                "refund_date": str(date.today()),
                "refund_method": "bank_transfer",
                "reference_number": "RFND-MANUAL-API",
                "reason": "Manual invoice allocation refund",
                "allocation_reversals": manual_reversals,
            },
        )
        assert create_refund_response.status_code == 201
        refund = create_refund_response.json()["data"]
        assert refund["allocation_reversals"][0]["invoice_number"] == "INV-PAYAPI-002"
        assert Decimal(refund["allocation_reversals"][0]["reversal_amount"]) == Decimal("1000.00")

    async def test_complete_payment_api_prefers_selected_invoice(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """API payment with preferred invoice should target it before smaller debts."""
        token, user_id, data = await self._setup_auth_and_data(db_session)

        smaller_invoice = Invoice(
            invoice_number="INV-PAYAPI-002",
            student_id=data["student"].id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("1000.00"),
            created_by_id=user_id,
        )
        smaller_invoice.lines = []
        db_session.add(smaller_invoice)
        await db_session.commit()

        create_response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "preferred_invoice_id": data["invoice"].id,
                "amount": "1000.00",
                "payment_method": "bank_transfer",
                "payment_date": str(date.today()),
                "reference": "targeted-payment",
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()["data"]
        assert created["preferred_invoice_id"] == data["invoice"].id
        assert created["preferred_invoice_number"] == data["invoice"].invoice_number

        payment_id = created["id"]
        complete_response = await client.post(
            f"/api/v1/payments/{payment_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert complete_response.status_code == 200

        preferred_invoice = await db_session.get(Invoice, data["invoice"].id)
        other_invoice = await db_session.get(Invoice, smaller_invoice.id)
        assert preferred_invoice is not None
        assert other_invoice is not None
        assert preferred_invoice.amount_due == Decimal("4000.00")
        assert other_invoice.amount_due == Decimal("1000.00")

    async def test_list_payments_api_includes_student_context(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Payments list API should expose student info and support search."""
        token, _, data = await self._setup_auth_and_data(db_session)

        await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "amount": "5000.00",
                "payment_method": "mpesa",
                "payment_date": str(date.today()),
                "reference": "MPESA-LIST-123",
            },
        )

        response = await client.get(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            params={"search": "STU-PAYAPI-001"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["total"] == 1
        row = result["data"]["items"][0]
        assert row["student_id"] == data["student"].id
        assert row["student_name"] == "API Student"
        assert row["student_number"] == "STU-PAYAPI-001"

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

    async def test_undo_reallocate_allocation_api_preserves_report_date(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """API Undo + reallocate should preserve allocation date for period reports."""
        token, user_id, data = await self._setup_auth_and_data(db_session)
        service = PaymentService(db_session)

        payment = await service.create_payment(
            PaymentCreate(
                student_id=data["student"].id,
                amount=Decimal("5000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date(2026, 1, 10),
                reference="api-undo-reallocate",
            ),
            received_by_id=user_id,
        )
        await service.complete_payment(payment.id, user_id)

        allocation_result = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        allocation = allocation_result.scalar_one()
        allocation_id = allocation.id
        allocation_amount = allocation.amount
        original_created_at = datetime(2026, 1, 10, 8, 0, tzinfo=timezone.utc)
        allocation.created_at = original_created_at
        await db_session.commit()

        response = await client.post(
            f"/api/v1/payments/allocations/{allocation_id}/undo-reallocate",
            headers={"Authorization": f"Bearer {token}"},
            params={"reason": "API test undo and reallocate"},
        )

        assert response.status_code == 200
        result = response.json()["data"]
        assert Decimal(result["total_allocated"]) == allocation_amount

        refreshed_allocations = await db_session.execute(
            select(CreditAllocation).where(
                CreditAllocation.student_id == data["student"].id
            )
        )
        allocations = list(refreshed_allocations.scalars().all())
        assert allocations
        assert sum(
            (
                item.amount
                for item in allocations
                if item.created_at.date() == original_created_at.date()
            ),
            Decimal("0.00"),
        ) == allocation_amount

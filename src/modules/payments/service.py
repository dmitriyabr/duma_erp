"""Service for Payments module."""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.shared.utils.money import round_money
from src.modules.payments.models import (
    CreditAllocation,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from src.modules.payments.schemas import (
    AllocationCreate,
    AllocationResponse,
    AutoAllocateRequest,
    AutoAllocateResult,
    PaymentCreate,
    PaymentFilters,
    PaymentUpdate,
    StatementEntry,
    StatementResponse,
    StudentBalance,
)
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.students.models import Student
from src.modules.reservations.service import ReservationService


class PaymentService:
    """Service for managing payments and credit allocations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # --- Payment Methods ---

    async def create_payment(
        self, data: PaymentCreate, received_by_id: int
    ) -> Payment:
        """Create a new payment (credit top-up)."""
        # Validate student exists
        student = await self._get_student(data.student_id)

        # Generate payment number
        number_gen = DocumentNumberGenerator(self.db)
        payment_number = await number_gen.generate("PAY")

        payment = Payment(
            payment_number=payment_number,
            student_id=data.student_id,
            amount=round_money(data.amount),
            payment_method=data.payment_method.value,
            payment_date=data.payment_date,
            reference=data.reference,
            confirmation_attachment_id=data.confirmation_attachment_id,
            status=PaymentStatus.PENDING.value,
            notes=data.notes,
            received_by_id=received_by_id,
        )
        self.db.add(payment)
        await self.db.flush()

        await self.audit.log(
            action="payment.create",
            entity_type="Payment",
            entity_id=payment.id,
            entity_identifier=payment_number,
            user_id=received_by_id,
            new_values={
                "student_id": data.student_id,
                "amount": str(data.amount),
                "payment_method": data.payment_method.value,
            },
        )

        await self.db.commit()
        return await self.get_payment_by_id(payment.id)

    async def get_payment_by_id(self, payment_id: int) -> Payment:
        """Get payment by ID with student (grade) and received_by loaded."""
        result = await self.db.execute(
            select(Payment)
            .where(Payment.id == payment_id)
            .options(
                selectinload(Payment.student).selectinload(Student.grade),
                selectinload(Payment.received_by),
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise NotFoundError(f"Payment with id {payment_id} not found")
        return payment

    async def list_payments(
        self, filters: PaymentFilters
    ) -> tuple[list[Payment], int]:
        """List payments with filters."""
        query = select(Payment)

        if filters.student_id:
            query = query.where(Payment.student_id == filters.student_id)
        if filters.status:
            query = query.where(Payment.status == filters.status.value)
        if filters.payment_method:
            query = query.where(Payment.payment_method == filters.payment_method.value)
        if filters.date_from:
            query = query.where(Payment.payment_date >= filters.date_from)
        if filters.date_to:
            query = query.where(Payment.payment_date <= filters.date_to)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(Payment.created_at.desc())
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)

        result = await self.db.execute(query)
        payments = list(result.scalars().all())

        return payments, total

    async def update_payment(
        self, payment_id: int, data: PaymentUpdate, updated_by_id: int
    ) -> Payment:
        """Update a pending payment."""
        payment = await self.get_payment_by_id(payment_id)

        if not payment.is_pending:
            raise ValidationError("Can only update pending payments")

        old_values = {}
        new_values = {}

        if data.amount is not None:
            old_values["amount"] = str(payment.amount)
            payment.amount = round_money(data.amount)
            new_values["amount"] = str(data.amount)

        if data.payment_method is not None:
            old_values["payment_method"] = payment.payment_method
            payment.payment_method = data.payment_method.value
            new_values["payment_method"] = data.payment_method.value

        if data.payment_date is not None:
            old_values["payment_date"] = str(payment.payment_date)
            payment.payment_date = data.payment_date
            new_values["payment_date"] = str(data.payment_date)

        if data.reference is not None:
            old_values["reference"] = payment.reference
            payment.reference = data.reference
            new_values["reference"] = data.reference

        if data.notes is not None:
            payment.notes = data.notes

        await self.audit.log(
            action="payment.update",
            entity_type="Payment",
            entity_id=payment_id,
            entity_identifier=payment.payment_number,
            user_id=updated_by_id,
            old_values=old_values,
            new_values=new_values,
        )

        await self.db.commit()
        return await self.get_payment_by_id(payment_id)

    async def complete_payment(
        self, payment_id: int, completed_by_id: int
    ) -> Payment:
        """Complete a pending payment - generates receipt number."""
        payment = await self.get_payment_by_id(payment_id)

        if not payment.is_pending:
            raise ValidationError("Can only complete pending payments")

        # Generate receipt number
        number_gen = DocumentNumberGenerator(self.db)
        receipt_number = await number_gen.generate("RCP")

        payment.status = PaymentStatus.COMPLETED.value
        payment.receipt_number = receipt_number

        await self.audit.log(
            action="payment.complete",
            entity_type="Payment",
            entity_id=payment_id,
            entity_identifier=payment.payment_number,
            user_id=completed_by_id,
            new_values={
                "status": PaymentStatus.COMPLETED.value,
                "receipt_number": receipt_number,
            },
        )

        await self.db.commit()
        return await self.get_payment_by_id(payment_id)

    async def cancel_payment(
        self, payment_id: int, cancelled_by_id: int, reason: str | None = None
    ) -> Payment:
        """Cancel a pending payment."""
        payment = await self.get_payment_by_id(payment_id)

        if not payment.is_pending:
            raise ValidationError("Can only cancel pending payments")

        payment.status = PaymentStatus.CANCELLED.value

        await self.audit.log(
            action="payment.cancel",
            entity_type="Payment",
            entity_id=payment_id,
            entity_identifier=payment.payment_number,
            user_id=cancelled_by_id,
            new_values={"status": PaymentStatus.CANCELLED.value},
            comment=reason,
        )

        await self.db.commit()
        return await self.get_payment_by_id(payment_id)

    # --- Credit Balance Methods ---

    async def get_student_balance(self, student_id: int) -> StudentBalance:
        """Get student's credit balance."""
        # Validate student exists
        await self._get_student(student_id)

        # Total completed payments
        payments_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.student_id == student_id,
                Payment.status == PaymentStatus.COMPLETED.value,
            )
        )
        total_payments = Decimal(str(payments_result.scalar() or 0))

        # Total allocations
        allocations_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.student_id == student_id
            )
        )
        total_allocated = Decimal(str(allocations_result.scalar() or 0))

        return StudentBalance(
            student_id=student_id,
            total_payments=round_money(total_payments),
            total_allocated=round_money(total_allocated),
            available_balance=round_money(total_payments - total_allocated),
        )

    # --- Allocation Methods ---

    async def allocate_manual(
        self, data: AllocationCreate, allocated_by_id: int
    ) -> CreditAllocation:
        """Manually allocate credit to an invoice."""
        # Validate student
        await self._get_student(data.student_id)

        # Validate invoice
        invoice = await self._get_invoice(data.invoice_id)
        if invoice.student_id != data.student_id:
            raise ValidationError("Invoice does not belong to this student")

        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
            raise ValidationError("Cannot allocate to cancelled/void invoice")

        if invoice.amount_due <= 0:
            raise ValidationError("Invoice is already fully paid")

        # Check available balance
        balance = await self.get_student_balance(data.student_id)
        if data.amount > balance.available_balance:
            raise ValidationError(
                f"Insufficient balance. Available: {balance.available_balance}, "
                f"Requested: {data.amount}"
            )

        # Check allocation doesn't exceed invoice amount_due
        if data.amount > invoice.amount_due:
            raise ValidationError(
                f"Allocation exceeds invoice amount due. "
                f"Amount due: {invoice.amount_due}, Requested: {data.amount}"
            )

        # Validate line if specified
        if data.invoice_line_id:
            line = await self._get_invoice_line(data.invoice_line_id)
            if line.invoice_id != data.invoice_id:
                raise ValidationError("Line does not belong to this invoice")
            if data.amount > line.remaining_amount:
                raise ValidationError(
                    f"Allocation exceeds line remaining amount. "
                    f"Remaining: {line.remaining_amount}, Requested: {data.amount}"
                )

        # Create allocation
        allocation = CreditAllocation(
            student_id=data.student_id,
            invoice_id=data.invoice_id,
            invoice_line_id=data.invoice_line_id,
            amount=round_money(data.amount),
            allocated_by_id=allocated_by_id,
        )
        self.db.add(allocation)
        await self.db.flush()

        # Update invoice paid amounts
        await self._update_invoice_paid_amounts(invoice)
        await self._sync_reservations_for_invoice(invoice.id, allocated_by_id)

        await self.audit.log(
            action="allocation.create",
            entity_type="CreditAllocation",
            entity_id=allocation.id,
            user_id=allocated_by_id,
            new_values={
                "student_id": data.student_id,
                "invoice_id": data.invoice_id,
                "amount": str(data.amount),
            },
        )

        await self.db.commit()
        return allocation

    async def allocate_auto(
        self, data: AutoAllocateRequest, allocated_by_id: int
    ) -> AutoAllocateResult:
        """
        Auto-allocate credit to invoices.

        Algorithm prioritizes full payment of invoices with products/special fees:
        1. Get all unpaid invoices with their lines (to check requires_full_payment)
        2. Split into two groups:
           - requires_full: invoices with products or admission fee (must be paid in full)
           - can_be_partial: regular service invoices (can be paid partially)
        3. First, process requires_full invoices (smallest first):
           - Only pay if we can pay in FULL (skip if not enough balance)
        4. Then, process can_be_partial invoices (smallest first):
           - Pay fully if possible, otherwise partial
        """
        # Validate student
        await self._get_student(data.student_id)

        # Get available balance
        balance = await self.get_student_balance(data.student_id)
        available = balance.available_balance

        if available <= 0:
            return AutoAllocateResult(
                total_allocated=Decimal("0.00"),
                invoices_fully_paid=0,
                invoices_partially_paid=0,
                remaining_balance=Decimal("0.00"),
                allocations=[],
            )

        # Limit to max_amount if specified
        max_to_allocate = (
            min(available, data.max_amount) if data.max_amount else available
        )
        remaining = max_to_allocate

        # Get unpaid invoices with lines loaded (needed for requires_full_payment check)
        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.student_id == data.student_id,
                Invoice.status.in_([
                    InvoiceStatus.ISSUED.value,
                    InvoiceStatus.PARTIALLY_PAID.value,
                ]),
                Invoice.amount_due > 0,
            )
            .options(
                selectinload(Invoice.lines).selectinload(InvoiceLine.kit),
            )
            .order_by(Invoice.amount_due.asc())
        )
        invoices = list(result.scalars().all())

        # Split into groups
        requires_full_invoices = []
        partial_ok_invoices = []

        for invoice in invoices:
            if invoice.requires_full_payment:
                requires_full_invoices.append(invoice)
            else:
                partial_ok_invoices.append(invoice)

        allocations = []
        fully_paid = 0
        partially_paid = 0

        # Helper to create allocation
        async def create_allocation(invoice: Invoice, amount: Decimal) -> AllocationResponse:
            allocation = CreditAllocation(
                student_id=data.student_id,
                invoice_id=invoice.id,
                invoice_line_id=None,
                amount=round_money(amount),
                allocated_by_id=allocated_by_id,
            )
            self.db.add(allocation)
            await self.db.flush()

            await self._update_invoice_paid_amounts(invoice)
            await self._sync_reservations_for_invoice(invoice.id, allocated_by_id)

            return AllocationResponse(
                id=allocation.id,
                student_id=allocation.student_id,
                invoice_id=allocation.invoice_id,
                invoice_line_id=allocation.invoice_line_id,
                amount=allocation.amount,
                allocated_by_id=allocation.allocated_by_id,
                created_at=allocation.created_at,
            )

        # Step 1: Process requires_full invoices (only pay if can pay in full)
        for invoice in requires_full_invoices:
            if remaining <= 0:
                break

            # Only allocate if we can pay in full
            if invoice.amount_due <= remaining:
                alloc_response = await create_allocation(invoice, invoice.amount_due)
                allocations.append(alloc_response)
                fully_paid += 1
                remaining -= invoice.amount_due
            # Skip if can't pay in full - don't partially pay products/admission

        # Step 2: Process partial_ok invoices (can pay partially)
        for invoice in partial_ok_invoices:
            if remaining <= 0:
                break

            amount_to_allocate = min(remaining, invoice.amount_due)
            alloc_response = await create_allocation(invoice, amount_to_allocate)
            allocations.append(alloc_response)

            if amount_to_allocate >= invoice.amount_due:
                fully_paid += 1
            else:
                partially_paid += 1

            remaining -= amount_to_allocate

        total_allocated = max_to_allocate - remaining

        await self.audit.log(
            action="allocation.auto",
            entity_type="Student",
            entity_id=data.student_id,
            user_id=allocated_by_id,
            new_values={
                "total_allocated": str(total_allocated),
                "invoices_fully_paid": fully_paid,
                "invoices_partially_paid": partially_paid,
            },
        )

        await self.db.commit()

        # Get updated balance
        updated_balance = await self.get_student_balance(data.student_id)

        return AutoAllocateResult(
            total_allocated=round_money(total_allocated),
            invoices_fully_paid=fully_paid,
            invoices_partially_paid=partially_paid,
            remaining_balance=updated_balance.available_balance,
            allocations=allocations,
        )

    async def delete_allocation(
        self, allocation_id: int, deleted_by_id: int, reason: str | None = None
    ) -> None:
        """Delete an allocation (return credit to balance)."""
        result = await self.db.execute(
            select(CreditAllocation).where(CreditAllocation.id == allocation_id)
        )
        allocation = result.scalar_one_or_none()
        if not allocation:
            raise NotFoundError(f"Allocation with id {allocation_id} not found")

        # Get the invoice to update
        invoice = await self._get_invoice(allocation.invoice_id)

        await self.audit.log(
            action="allocation.delete",
            entity_type="CreditAllocation",
            entity_id=allocation_id,
            user_id=deleted_by_id,
            old_values={
                "student_id": allocation.student_id,
                "invoice_id": allocation.invoice_id,
                "amount": str(allocation.amount),
            },
            comment=reason,
        )

        await self.db.delete(allocation)
        await self.db.flush()

        # Update invoice paid amounts
        await self._update_invoice_paid_amounts(invoice)
        await self._sync_reservations_for_invoice(invoice.id, deleted_by_id)

        await self.db.commit()

    # --- Statement Methods ---

    async def get_statement(
        self,
        student_id: int,
        date_from: date,
        date_to: date,
    ) -> StatementResponse:
        """Generate account statement for a student."""
        student = await self._get_student(student_id)

        # Get opening balance (sum of all transactions before date_from)
        opening_payments = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.student_id == student_id,
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date < date_from,
            )
        )
        opening_credits = Decimal(str(opening_payments.scalar() or 0))

        opening_allocations = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.student_id == student_id,
                func.date(CreditAllocation.created_at) < date_from,
            )
        )
        opening_debits = Decimal(str(opening_allocations.scalar() or 0))

        opening_balance = round_money(opening_credits - opening_debits)

        # Get payments in period
        payments_result = await self.db.execute(
            select(Payment)
            .where(
                Payment.student_id == student_id,
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to,
            )
            .order_by(Payment.payment_date, Payment.created_at)
        )
        payments = list(payments_result.scalars().all())

        # Get allocations in period
        allocations_result = await self.db.execute(
            select(CreditAllocation)
            .where(
                CreditAllocation.student_id == student_id,
                func.date(CreditAllocation.created_at) >= date_from,
                func.date(CreditAllocation.created_at) <= date_to,
            )
            .options(selectinload(CreditAllocation.invoice))
            .order_by(CreditAllocation.created_at)
        )
        allocations = list(allocations_result.scalars().all())

        # Merge and sort by date
        entries: list[StatementEntry] = []
        running_balance = opening_balance
        total_credits = Decimal("0.00")
        total_debits = Decimal("0.00")

        def _to_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        # Convert to entries with unified datetime for sorting
        all_items: list[tuple[datetime, str, Payment | CreditAllocation]] = []

        for payment in payments:
            dt = datetime.combine(
                payment.payment_date, datetime.min.time(), tzinfo=timezone.utc
            )
            all_items.append((dt, "payment", payment))

        for allocation in allocations:
            all_items.append((_to_utc(allocation.created_at), "allocation", allocation))

        # Sort by datetime
        all_items.sort(key=lambda x: x[0])

        for dt, item_type, item in all_items:
            if item_type == "payment":
                payment = item
                running_balance += payment.amount
                total_credits += payment.amount
                entries.append(
                    StatementEntry(
                        date=dt,
                        description=f"Payment - {payment.payment_method.upper()}",
                        reference=payment.receipt_number or payment.payment_number,
                        credit=payment.amount,
                        debit=None,
                        balance=round_money(running_balance),
                    )
                )
            else:
                allocation = item
                running_balance -= allocation.amount
                total_debits += allocation.amount
                invoice = allocation.invoice
                entries.append(
                    StatementEntry(
                        date=dt,
                        description=f"Payment to {invoice.invoice_number}",
                        reference=invoice.invoice_number,
                        credit=None,
                        debit=allocation.amount,
                        balance=round_money(running_balance),
                    )
                )

        return StatementResponse(
            student_id=student_id,
            student_name=student.full_name,
            period_from=date_from,
            period_to=date_to,
            opening_balance=opening_balance,
            total_credits=round_money(total_credits),
            total_debits=round_money(total_debits),
            closing_balance=round_money(running_balance),
            entries=entries,
        )

    # --- Helper Methods ---

    async def _get_student(self, student_id: int) -> Student:
        """Get student by ID."""
        result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    async def _get_invoice(self, invoice_id: int) -> Invoice:
        """Get invoice by ID with lines loaded."""
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(selectinload(Invoice.lines))
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError(f"Invoice with id {invoice_id} not found")
        return invoice

    async def _get_invoice_line(self, line_id: int) -> InvoiceLine:
        """Get invoice line by ID."""
        result = await self.db.execute(
            select(InvoiceLine).where(InvoiceLine.id == line_id)
        )
        line = result.scalar_one_or_none()
        if not line:
            raise NotFoundError(f"Invoice line with id {line_id} not found")
        return line

    async def _update_invoice_paid_amounts(self, invoice: Invoice) -> None:
        """Update invoice paid_total and amount_due based on allocations."""
        # Get total allocations for this invoice
        result = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.invoice_id == invoice.id
            )
        )
        total_paid = Decimal(str(result.scalar() or 0))

        invoice.paid_total = round_money(total_paid)
        invoice.amount_due = round_money(invoice.total - total_paid)

        # Update status
        if invoice.amount_due <= 0:
            invoice.status = InvoiceStatus.PAID.value
        elif total_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID.value

        # Also update line paid amounts if we have line-level allocations
        for line in invoice.lines:
            line_result = await self.db.execute(
                select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                    CreditAllocation.invoice_line_id == line.id
                )
            )
            line_paid = Decimal(str(line_result.scalar() or 0))

            # If no line-level allocations, distribute proportionally
            if line_paid == 0 and total_paid > 0:
                # Proportional distribution based on net_amount
                if invoice.total > 0:
                    proportion = line.net_amount / invoice.total
                    line_paid = round_money(total_paid * proportion)

            line.paid_amount = round_money(line_paid)
            line.remaining_amount = round_money(line.net_amount - line_paid)

    async def _sync_reservations_for_invoice(self, invoice_id: int, user_id: int) -> None:
        """Create/cancel reservations based on paid status of invoice lines."""
        reservation_service = ReservationService(self.db)
        await reservation_service.sync_for_invoice(invoice_id=invoice_id, user_id=user_id)

"""Service for Payments module."""

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from itertools import groupby

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.shared.utils.money import round_money
from src.modules.billing_accounts.models import BillingAccount
from src.modules.billing_accounts.service import BillingAccountService
from src.modules.payments.models import (
    CreditAllocation,
    Payment,
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
from src.modules.terms.models import Term, TermStatus
from src.modules.reservations.service import ReservationService


class PaymentService:
    """Service for managing payments and credit allocations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    @staticmethod
    def _money_to_cents(value: Decimal) -> int:
        return int((round_money(value) * 100).to_integral_value())

    @staticmethod
    def _cents_to_money(value: int) -> Decimal:
        return round_money(Decimal(value) / Decimal("100"))

    def _allocate_proportionally(
        self,
        total: Decimal,
        capacities: dict[int, Decimal],
    ) -> tuple[dict[int, Decimal], Decimal]:
        """Distribute invoice-level paid amount across line capacities by net remaining."""
        allocations = {key: Decimal("0.00") for key in capacities}
        total = round_money(total)
        if total <= 0:
            return allocations, Decimal("0.00")

        capacity_cents = {
            key: max(0, self._money_to_cents(value))
            for key, value in capacities.items()
        }
        total_capacity_cents = sum(capacity_cents.values())
        if total_capacity_cents <= 0:
            return allocations, total

        total_cents = max(0, self._money_to_cents(total))
        if total_cents >= total_capacity_cents:
            for key, cents in capacity_cents.items():
                allocations[key] = self._cents_to_money(cents)
            return allocations, self._cents_to_money(total_cents - total_capacity_cents)

        allocated_cents = {key: 0 for key in capacities}
        remainders: list[tuple[Decimal, int]] = []
        used_cents = 0

        for key, cap_cents in capacity_cents.items():
            if cap_cents <= 0:
                continue
            raw_share = Decimal(total_cents) * Decimal(cap_cents) / Decimal(total_capacity_cents)
            base_cents = min(cap_cents, int(raw_share))
            allocated_cents[key] = base_cents
            used_cents += base_cents
            remainders.append((raw_share - Decimal(base_cents), key))

        leftover_cents = total_cents - used_cents
        remainders.sort(key=lambda row: (row[0], row[1]), reverse=True)
        while leftover_cents > 0:
            updated = False
            for _, key in remainders:
                if leftover_cents <= 0:
                    break
                if allocated_cents[key] >= capacity_cents[key]:
                    continue
                allocated_cents[key] += 1
                leftover_cents -= 1
                updated = True
            if not updated:
                break

        for key, cents in allocated_cents.items():
            allocations[key] = self._cents_to_money(cents)

        return allocations, self._cents_to_money(leftover_cents)

    async def _resolve_billing_context(
        self,
        *,
        student_id: int | None,
        billing_account_id: int | None,
    ) -> tuple[BillingAccount, Student]:
        """Resolve owner account plus a reference student for compatibility."""
        billing_account_service = BillingAccountService(self.db)

        if student_id is not None:
            await billing_account_service.ensure_student_billing_account(student_id)
            student = await self._get_student(student_id)
            if student.billing_account_id is None:
                raise ValidationError("Student has no billing account")
            account = await self._get_billing_account(student.billing_account_id)
            if billing_account_id is not None and account.id != billing_account_id:
                raise ValidationError("Student does not belong to this billing account")
            return account, student

        if billing_account_id is None:
            raise ValidationError("Either student_id or billing_account_id is required")

        account = await self._get_billing_account(billing_account_id)
        reference_student = next((student for student in account.students), None)
        if reference_student is None:
            raise ValidationError("Billing account has no linked students")
        return account, reference_student

    # --- Payment Methods ---

    async def create_payment(
        self, data: PaymentCreate, received_by_id: int
    ) -> Payment:
        """Create a new payment (credit top-up)."""
        account, reference_student = await self._resolve_billing_context(
            student_id=data.student_id,
            billing_account_id=data.billing_account_id,
        )
        await self._validate_preferred_invoice(account.id, data.preferred_invoice_id)

        # Generate payment number
        number_gen = DocumentNumberGenerator(self.db)
        payment_number = await number_gen.generate("PAY")

        payment = Payment(
            payment_number=payment_number,
            student_id=reference_student.id,
            billing_account_id=account.id,
            preferred_invoice_id=data.preferred_invoice_id,
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
                "student_id": reference_student.id,
                "billing_account_id": account.id,
                "preferred_invoice_id": data.preferred_invoice_id,
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
                selectinload(Payment.billing_account).selectinload(BillingAccount.students),
                selectinload(Payment.preferred_invoice),
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
        query = (
            select(Payment)
            .options(
                selectinload(Payment.student),
                selectinload(Payment.billing_account).selectinload(BillingAccount.students),
                selectinload(Payment.preferred_invoice),
                selectinload(Payment.received_by),
            )
        )

        if filters.student_id is not None:
            account, _ = await self._resolve_billing_context(
                student_id=filters.student_id,
                billing_account_id=filters.billing_account_id,
            )
            query = query.where(Payment.billing_account_id == account.id)
        elif filters.billing_account_id is not None:
            query = query.where(Payment.billing_account_id == filters.billing_account_id)
        if filters.status:
            query = query.where(Payment.status == filters.status.value)
        if filters.payment_method:
            query = query.where(Payment.payment_method == filters.payment_method.value)
        if filters.search and filters.search.strip():
            search_term = f"%{filters.search.strip()}%"
            account_student_match = exists(
                select(Student.id).where(
                    Student.billing_account_id == Payment.billing_account_id,
                    or_(
                        Student.first_name.ilike(search_term),
                        Student.last_name.ilike(search_term),
                        Student.student_number.ilike(search_term),
                    ),
                )
            )
            query = query.join(Payment.billing_account).where(
                or_(
                    Payment.payment_number.ilike(search_term),
                    Payment.receipt_number.ilike(search_term),
                    Payment.reference.ilike(search_term),
                    BillingAccount.account_number.ilike(search_term),
                    BillingAccount.display_name.ilike(search_term),
                    account_student_match,
                )
            )
        if filters.date_from:
            query = query.where(Payment.payment_date >= filters.date_from)
        if filters.date_to:
            query = query.where(Payment.payment_date <= filters.date_to)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.order_by(Payment.payment_date.desc(), Payment.created_at.desc())
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

        if "preferred_invoice_id" in data.model_fields_set:
            old_values["preferred_invoice_id"] = payment.preferred_invoice_id
            await self._validate_preferred_invoice(
                payment.billing_account_id,
                data.preferred_invoice_id,
            )
            payment.preferred_invoice_id = data.preferred_invoice_id
            new_values["preferred_invoice_id"] = data.preferred_invoice_id

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

        await self._validate_preferred_invoice(
            payment.billing_account_id,
            payment.preferred_invoice_id,
        )

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

        # Update cached credit balance (recalculate)
        await self._update_billing_account_balance_cache(payment.billing_account_id)

        await self.db.commit()
        targeted_amount = Decimal("0.00")
        if payment.preferred_invoice_id is not None:
            preferred_invoice = await self._get_invoice(payment.preferred_invoice_id)
            targeted_amount = min(payment.amount, preferred_invoice.amount_due)
            if targeted_amount > 0:
                await self.allocate_manual(
                    AllocationCreate(
                        billing_account_id=payment.billing_account_id,
                        invoice_id=preferred_invoice.id,
                        amount=targeted_amount,
                    ),
                    completed_by_id,
                )

        remaining_to_auto_allocate = round_money(payment.amount - targeted_amount)
        if remaining_to_auto_allocate > 0:
            await self.allocate_auto(
                AutoAllocateRequest(
                    billing_account_id=payment.billing_account_id,
                    max_amount=remaining_to_auto_allocate,
                ),
                completed_by_id,
            )
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
        """Get student's credit balance from cache."""
        student = await self._get_student(student_id)
        if student.billing_account_id is None:
            billing_account_service = BillingAccountService(self.db)
            await billing_account_service.ensure_student_billing_account(student.id)
            student = await self._get_student(student_id)
        account = await self._get_billing_account(student.billing_account_id)

        available_balance = round_money(account.cached_credit_balance)

        payments_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.billing_account_id == account.id,
                Payment.status == PaymentStatus.COMPLETED.value,
            )
        )
        total_payments = Decimal(str(payments_result.scalar() or 0))

        allocations_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.billing_account_id == account.id
            )
        )
        total_allocated = Decimal(str(allocations_result.scalar() or 0))

        return StudentBalance(
            student_id=student_id,
            billing_account_id=account.id,
            billing_account_number=account.account_number,
            billing_account_name=account.display_name,
            total_payments=round_money(total_payments),
            total_allocated=round_money(total_allocated),
            available_balance=available_balance,
        )

    async def get_student_balances_batch(
        self, student_ids: list[int]
    ) -> list[StudentBalance]:
        """Get credit balances for multiple students in one go (uses cache)."""
        if not student_ids:
            return []

        students_result = await self.db.execute(
            select(Student)
            .where(Student.id.in_(student_ids))
            .options(selectinload(Student.billing_account))
        )
        students = {student.id: student for student in students_result.scalars().unique().all()}
        account_ids = sorted(
            {
                student.billing_account_id
                for student in students.values()
                if student.billing_account_id is not None
            }
        )

        payments_result = await self.db.execute(
            select(Payment.billing_account_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(
                Payment.billing_account_id.in_(account_ids),
                Payment.status == PaymentStatus.COMPLETED.value,
            )
            .group_by(Payment.billing_account_id)
        )
        payments_by_account = {row[0]: Decimal(str(row[1])) for row in payments_result.all()}

        allocations_result = await self.db.execute(
            select(
                CreditAllocation.billing_account_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0),
            )
            .where(CreditAllocation.billing_account_id.in_(account_ids))
            .group_by(CreditAllocation.billing_account_id)
        )
        allocations_by_account = {row[0]: Decimal(str(row[1])) for row in allocations_result.all()}

        return [
            StudentBalance(
                student_id=sid,
                billing_account_id=students[sid].billing_account_id if sid in students else None,
                billing_account_number=students[sid].billing_account.account_number
                if sid in students and students[sid].billing_account
                else None,
                billing_account_name=students[sid].billing_account.display_name
                if sid in students and students[sid].billing_account
                else None,
                total_payments=round_money(
                    payments_by_account.get(
                        students[sid].billing_account_id if sid in students else None,
                        Decimal("0"),
                    )
                ),
                total_allocated=round_money(
                    allocations_by_account.get(
                        students[sid].billing_account_id if sid in students else None,
                        Decimal("0"),
                    )
                ),
                available_balance=round_money(
                    students[sid].billing_account.cached_credit_balance
                    if sid in students and students[sid].billing_account
                    else Decimal("0")
                ),
            )
            for sid in student_ids
        ]

    # --- Allocation Methods ---

    async def allocate_manual(
        self, data: AllocationCreate, allocated_by_id: int
    ) -> CreditAllocation:
        """Manually allocate credit to an invoice."""
        account, _ = await self._resolve_billing_context(
            student_id=data.student_id,
            billing_account_id=data.billing_account_id,
        )

        # Validate invoice
        invoice = await self._get_invoice(data.invoice_id)
        if invoice.billing_account_id != account.id:
            raise ValidationError("Invoice does not belong to this billing account")

        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
            raise ValidationError("Cannot allocate to cancelled/void invoice")

        if invoice.amount_due <= 0:
            raise ValidationError("Invoice is already fully paid")

        # Check available balance
        balance = await self.get_student_balance(invoice.student_id)
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
            student_id=invoice.student_id,
            billing_account_id=account.id,
            invoice_id=data.invoice_id,
            invoice_line_id=data.invoice_line_id,
            amount=round_money(data.amount),
            allocated_by_id=allocated_by_id,
        )
        self.db.add(allocation)
        await self.db.flush()

        await self._update_billing_account_balance_cache(account.id)

        # Update invoice paid amounts
        await self._update_invoice_paid_amounts(invoice)
        await self._sync_reservations_for_invoice(invoice.id, allocated_by_id)

        await self.audit.log(
            action="allocation.create",
            entity_type="CreditAllocation",
            entity_id=allocation.id,
            user_id=allocated_by_id,
            new_values={
                "student_id": invoice.student_id,
                "billing_account_id": account.id,
                "invoice_id": data.invoice_id,
                "amount": str(data.amount),
            },
        )

        await self.db.commit()
        return allocation

    async def allocate_auto(
        self,
        data: AutoAllocateRequest,
        allocated_by_id: int,
        *,
        allocation_created_at: datetime | None = None,
        commit: bool = True,
    ) -> AutoAllocateResult:
        """
        Auto-allocate credit to invoices.

        Algorithm:
        1. Older term debt first, then active/current term, then future/no-term invoices.
        2. Within each term bucket, requires_full invoices are paid first.
        3. Other invoices in the same bucket share remaining balance proportionally by amount_due.
        """
        account, reference_student = await self._resolve_billing_context(
            student_id=data.student_id,
            billing_account_id=data.billing_account_id,
        )

        # Get available balance
        balance = await self.get_student_balance(reference_student.id)
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
        active_term = await self._get_active_term()
        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.billing_account_id == account.id,
                Invoice.status.in_([
                    InvoiceStatus.ISSUED.value,
                    InvoiceStatus.PARTIALLY_PAID.value,
                ]),
                Invoice.amount_due > 0,
            )
            .options(
                selectinload(Invoice.lines).selectinload(InvoiceLine.kit),
                selectinload(Invoice.term),
            )
        )
        invoices = list(result.scalars().all())

        allocations = []
        fully_paid = 0
        partially_paid = 0

        # Helper to create allocation
        async def create_allocation(invoice: Invoice, amount: Decimal) -> AllocationResponse:
            allocation_values = {
                "student_id": invoice.student_id,
                "billing_account_id": account.id,
                "invoice_id": invoice.id,
                "invoice_line_id": None,
                "amount": round_money(amount),
                "allocated_by_id": allocated_by_id,
            }
            if allocation_created_at is not None:
                allocation_values["created_at"] = allocation_created_at
            allocation = CreditAllocation(**allocation_values)
            self.db.add(allocation)
            await self.db.flush()

            await self._update_invoice_paid_amounts(invoice)
            await self._sync_reservations_for_invoice(invoice.id, allocated_by_id)

            return AllocationResponse(
                id=allocation.id,
                student_id=allocation.student_id,
                billing_account_id=allocation.billing_account_id,
                invoice_id=allocation.invoice_id,
                invoice_line_id=allocation.invoice_line_id,
                amount=allocation.amount,
                allocated_by_id=allocation.allocated_by_id,
                created_at=allocation.created_at,
            )

        sorted_invoices = sorted(
            invoices,
            key=lambda invoice: self._allocation_priority_key(invoice, active_term),
        )

        for _, term_invoices_iter in groupby(
            sorted_invoices,
            key=lambda invoice: self._allocation_term_bucket(invoice, active_term),
        ):
            if remaining <= 0:
                break

            term_invoices = list(term_invoices_iter)
            requires_full_invoices = [
                invoice for invoice in term_invoices if invoice.requires_full_payment
            ]
            partial_ok_invoices = [
                invoice for invoice in term_invoices if not invoice.requires_full_payment
            ]

            # Step 1: requires_full invoices first inside the term bucket.
            for invoice in requires_full_invoices:
                if remaining <= 0:
                    break
                due_before = round_money(invoice.amount_due)
                amount_to_allocate = min(remaining, due_before)
                alloc_response = await create_allocation(invoice, amount_to_allocate)
                allocations.append(alloc_response)
                if amount_to_allocate >= due_before:
                    fully_paid += 1
                else:
                    partially_paid += 1
                remaining = round_money(remaining - amount_to_allocate)

            # Step 2: partial_ok invoices share remaining balance proportionally in this bucket.
            if partial_ok_invoices and remaining > 0:
                invoice_by_id = {invoice.id: invoice for invoice in partial_ok_invoices}
                capacities = {
                    invoice.id: round_money(invoice.amount_due)
                    for invoice in partial_ok_invoices
                    if invoice.amount_due > 0
                }
                amounts_by_invoice_id, _ = self._allocate_proportionally(remaining, capacities)
                for invoice_id, amount in amounts_by_invoice_id.items():
                    amount = round_money(amount)
                    if amount <= 0:
                        continue
                    invoice = invoice_by_id[invoice_id]
                    due_before = round_money(invoice.amount_due)
                    alloc_response = await create_allocation(invoice, amount)
                    allocations.append(alloc_response)
                    if amount >= due_before:
                        fully_paid += 1
                    else:
                        partially_paid += 1
                    remaining = round_money(remaining - amount)

        total_allocated = max_to_allocate - remaining
        await self._update_billing_account_balance_cache(account.id)

        await self.audit.log(
            action="allocation.auto",
            entity_type="BillingAccount",
            entity_id=account.id,
            user_id=allocated_by_id,
            new_values={
                "total_allocated": str(total_allocated),
                "invoices_fully_paid": fully_paid,
                "invoices_partially_paid": partially_paid,
            },
        )

        if commit:
            await self.db.commit()
        else:
            await self.db.flush()

        # Get updated balance
        updated_balance = await self.get_student_balance(reference_student.id)

        return AutoAllocateResult(
            total_allocated=round_money(total_allocated),
            invoices_fully_paid=fully_paid,
            invoices_partially_paid=partially_paid,
            remaining_balance=updated_balance.available_balance,
            allocations=allocations,
        )

    async def _get_active_term(self) -> Term | None:
        result = await self.db.execute(
            select(Term).where(Term.status == TermStatus.ACTIVE.value)
        )
        return result.scalar_one_or_none()

    def _allocation_term_bucket(
        self,
        invoice: Invoice,
        active_term: Term | None,
    ) -> tuple[int, int, int]:
        """Return a sortable bucket where older academic debt wins before current debt."""
        term = invoice.term

        if term is not None:
            if active_term is not None:
                invoice_key = (term.year, term.term_number)
                active_key = (active_term.year, active_term.term_number)
                if invoice_key < active_key:
                    bucket = 0
                elif invoice_key == active_key:
                    bucket = 1
                else:
                    bucket = 2
            elif term.status == TermStatus.CLOSED.value:
                bucket = 0
            else:
                bucket = 1
            return (bucket, term.year, term.term_number)

        if active_term is not None and active_term.start_date is not None:
            invoice_date = invoice.due_date or invoice.issue_date
            if invoice_date is not None and invoice_date < active_term.start_date:
                return (0, 9999, 99)

        return (3, 9999, 99)

    def _allocation_priority_key(
        self,
        invoice: Invoice,
        active_term: Term | None,
    ) -> tuple[int, int, int, date, int]:
        fallback_date = invoice.due_date or invoice.issue_date or date.max
        return (*self._allocation_term_bucket(invoice, active_term), fallback_date, invoice.id)

    async def delete_allocation(
        self,
        allocation_id: int,
        deleted_by_id: int,
        reason: str | None = None,
        *,
        commit: bool = True,
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

        await self._update_billing_account_balance_cache(allocation.billing_account_id)

        # Update invoice paid amounts
        await self._update_invoice_paid_amounts(invoice)
        await self._sync_reservations_for_invoice(invoice.id, deleted_by_id)

        if commit:
            await self.db.commit()

    async def undo_and_reallocate_allocation(
        self,
        allocation_id: int,
        allocated_by_id: int,
        reason: str | None = None,
    ) -> AutoAllocateResult:
        """Undo one allocation and re-run auto-allocation without moving report period."""
        result = await self.db.execute(
            select(CreditAllocation).where(CreditAllocation.id == allocation_id)
        )
        allocation = result.scalar_one_or_none()
        if not allocation:
            raise NotFoundError(f"Allocation with id {allocation_id} not found")

        billing_account_id = allocation.billing_account_id
        allocation_created_at = allocation.created_at

        await self.delete_allocation(
            allocation_id,
            allocated_by_id,
            reason or "Undo allocation before reallocation",
            commit=False,
        )
        result = await self.allocate_auto(
            AutoAllocateRequest(billing_account_id=billing_account_id),
            allocated_by_id=allocated_by_id,
            allocation_created_at=allocation_created_at,
            commit=False,
        )
        await self.db.commit()
        return result

    # --- Statement Methods ---

    async def get_statement(
        self,
        student_id: int,
        date_from: date,
        date_to: date,
    ) -> StatementResponse:
        """Generate account statement for a student."""
        student = await self._get_student(student_id)
        if student.billing_account_id is None:
            billing_account_service = BillingAccountService(self.db)
            await billing_account_service.ensure_student_billing_account(student.id)
            student = await self._get_student(student_id)
        return await self.get_billing_account_statement(
            student.billing_account_id,
            date_from,
            date_to,
            reference_student=student,
        )

    async def get_billing_account_statement(
        self,
        billing_account_id: int,
        date_from: date,
        date_to: date,
        reference_student: Student | None = None,
    ) -> StatementResponse:
        """Generate account statement for a billing account."""
        account = await self._get_billing_account(billing_account_id)
        if reference_student is None:
            reference_student = next((student for student in account.students), None)
        if reference_student is None:
            raise ValidationError("Billing account has no linked students")

        # Get opening balance (sum of all transactions before date_from)
        opening_payments = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.billing_account_id == billing_account_id,
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.payment_date < date_from,
            )
        )
        opening_credits = Decimal(str(opening_payments.scalar() or 0))

        opening_allocations = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.billing_account_id == billing_account_id,
                func.date(CreditAllocation.created_at) < date_from,
            )
        )
        opening_debits = Decimal(str(opening_allocations.scalar() or 0))

        opening_balance = round_money(opening_credits - opening_debits)

        # Get payments in period
        payments_result = await self.db.execute(
            select(Payment)
            .where(
                Payment.billing_account_id == billing_account_id,
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
                CreditAllocation.billing_account_id == billing_account_id,
                func.date(CreditAllocation.created_at) >= date_from,
                func.date(CreditAllocation.created_at) <= date_to,
            )
            .options(
                selectinload(CreditAllocation.invoice).selectinload(Invoice.student)
            )
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
                        entry_type="payment",
                        description=f"Payment - {payment.payment_method.upper()} ({account.display_name})",
                        reference=payment.receipt_number or payment.payment_number,
                        payment_id=payment.id,
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
                        entry_type="allocation",
                        description=f"Payment to {invoice.invoice_number} ({invoice.student.full_name})",
                        reference=invoice.invoice_number,
                        allocation_id=allocation.id,
                        invoice_id=invoice.id,
                        credit=None,
                        debit=allocation.amount,
                        balance=round_money(running_balance),
                    )
                )

        return StatementResponse(
            student_id=reference_student.id,
            student_name=reference_student.full_name,
            billing_account_id=account.id,
            billing_account_number=account.account_number,
            billing_account_name=account.display_name,
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
            select(Student)
            .where(Student.id == student_id)
            .options(selectinload(Student.billing_account))
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    async def _get_billing_account(self, billing_account_id: int) -> BillingAccount:
        result = await self.db.execute(
            select(BillingAccount)
            .where(BillingAccount.id == billing_account_id)
            .options(selectinload(BillingAccount.students))
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(f"Billing account with id {billing_account_id} not found")
        return account

    async def _get_invoice(self, invoice_id: int) -> Invoice:
        """Get invoice by ID with lines loaded."""
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.student),
                selectinload(Invoice.billing_account),
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError(f"Invoice with id {invoice_id} not found")
        return invoice

    async def _validate_preferred_invoice(
        self,
        billing_account_id: int,
        preferred_invoice_id: int | None,
    ) -> None:
        if preferred_invoice_id is None:
            return

        invoice = await self._get_invoice(preferred_invoice_id)
        if invoice.billing_account_id != billing_account_id:
            raise ValidationError("Preferred invoice does not belong to this billing account")
        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
            raise ValidationError("Preferred invoice cannot be cancelled or void")
        if invoice.amount_due <= Decimal("0.00"):
            raise ValidationError("Preferred invoice is already fully paid")

    async def _get_invoice_line(self, line_id: int) -> InvoiceLine:
        """Get invoice line by ID."""
        result = await self.db.execute(
            select(InvoiceLine).where(InvoiceLine.id == line_id)
        )
        line = result.scalar_one_or_none()
        if not line:
            raise NotFoundError(f"Invoice line with id {line_id} not found")
        return line

    async def _sum_invoice_allocations(self, invoice_id: int) -> Decimal:
        result = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.invoice_id == invoice_id
            )
        )
        return round_money(Decimal(str(result.scalar() or 0)))

    async def _reduce_allocations(
        self,
        allocations: list[CreditAllocation],
        amount_to_release: Decimal,
        user_id: int,
        reason: str,
    ) -> Decimal:
        released = Decimal("0.00")
        remaining = round_money(amount_to_release)

        for allocation in allocations:
            if remaining <= 0:
                break

            release_amount = min(remaining, allocation.amount)
            if release_amount <= 0:
                continue

            old_amount = round_money(allocation.amount)
            new_amount = round_money(old_amount - release_amount)
            await self.audit.log(
                action="allocation.auto_deallocate",
                entity_type="CreditAllocation",
                entity_id=allocation.id,
                user_id=user_id,
                old_values={"amount": str(old_amount)},
                new_values={"amount": str(new_amount)},
                comment=reason,
            )

            if new_amount <= 0:
                await self.db.delete(allocation)
            else:
                allocation.amount = new_amount

            released = round_money(released + release_amount)
            remaining = round_money(remaining - release_amount)

        await self.db.flush()
        return released

    async def release_excess_allocations(
        self,
        invoice_id: int,
        user_id: int,
        reason: str,
    ) -> Decimal:
        """Return excess invoice allocations back to student credit after totals shrink."""
        invoice = await self._get_invoice(invoice_id)
        if not invoice.lines:
            return Decimal("0.00")

        invoice.subtotal = round_money(sum(line.line_total for line in invoice.lines))
        invoice.discount_total = round_money(
            sum(line.discount_amount for line in invoice.lines)
        )
        invoice.total = round_money(invoice.subtotal - invoice.discount_total)

        allocations_result = await self.db.execute(
            select(CreditAllocation)
            .where(CreditAllocation.invoice_id == invoice.id)
            .order_by(CreditAllocation.created_at.desc(), CreditAllocation.id.desc())
        )
        allocations = list(allocations_result.scalars().all())
        if not allocations:
            return Decimal("0.00")

        allocations_by_line: dict[int, list[CreditAllocation]] = defaultdict(list)
        invoice_level_allocations: list[CreditAllocation] = []
        for allocation in allocations:
            if allocation.invoice_line_id is None:
                invoice_level_allocations.append(allocation)
            else:
                allocations_by_line[int(allocation.invoice_line_id)].append(allocation)

        released_total = Decimal("0.00")

        # First, cap explicit line-level allocations to each line's current net amount.
        for line in invoice.lines:
            line_allocations = allocations_by_line.get(line.id, [])
            if not line_allocations:
                continue

            explicit_total = round_money(
                sum((allocation.amount for allocation in line_allocations), Decimal("0.00"))
            )
            line_excess = round_money(max(Decimal("0.00"), explicit_total - line.net_amount))
            if line_excess <= 0:
                continue

            released_total = round_money(
                released_total
                + await self._reduce_allocations(
                    line_allocations,
                    line_excess,
                    user_id,
                    f"{reason} (line_id={line.id})",
                )
            )

        # Then, if invoice total is still over-allocated, release invoice-level allocations.
        total_allocated = await self._sum_invoice_allocations(invoice.id)
        invoice_excess = round_money(max(Decimal("0.00"), total_allocated - invoice.total))
        if invoice_excess > 0 and invoice_level_allocations:
            released_total = round_money(
                released_total
                + await self._reduce_allocations(
                    invoice_level_allocations,
                    invoice_excess,
                    user_id,
                    reason,
                )
            )

        # Final fallback for any historical oddities: trim newest remaining allocations.
        total_allocated = await self._sum_invoice_allocations(invoice.id)
        invoice_excess = round_money(max(Decimal("0.00"), total_allocated - invoice.total))
        if invoice_excess > 0:
            remaining_allocations_result = await self.db.execute(
                select(CreditAllocation)
                .where(CreditAllocation.invoice_id == invoice.id)
                .order_by(CreditAllocation.created_at.desc(), CreditAllocation.id.desc())
            )
            remaining_allocations = list(remaining_allocations_result.scalars().all())
            released_total = round_money(
                released_total
                + await self._reduce_allocations(
                    remaining_allocations,
                    invoice_excess,
                    user_id,
                    f"{reason} (fallback)",
                )
            )

        if released_total > 0:
            await self._update_billing_account_balance_cache(invoice.billing_account_id)
            await self._update_invoice_paid_amounts(invoice)

        return round_money(released_total)

    async def _update_invoice_paid_amounts(self, invoice: Invoice) -> None:
        """Update invoice paid_total and amount_due based on allocations."""
        if invoice.lines:
            invoice.subtotal = round_money(sum(line.line_total for line in invoice.lines))
            invoice.discount_total = round_money(
                sum(line.discount_amount for line in invoice.lines)
            )
            invoice.total = round_money(invoice.subtotal - invoice.discount_total)

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
        if invoice.status not in (
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.VOID.value,
            InvoiceStatus.DRAFT.value,
        ):
            if invoice.amount_due <= 0:
                invoice.status = InvoiceStatus.PAID.value
            elif total_paid > 0:
                invoice.status = InvoiceStatus.PARTIALLY_PAID.value
            else:
                invoice.status = InvoiceStatus.ISSUED.value

        # Also update line paid amounts if we have line-level allocations
        # OPTIMIZATION: Batch query instead of N+1 queries in loop
        if invoice.lines:
            line_ids = [line.id for line in invoice.lines]

            # Get all line-level allocations in one query (GROUP BY)
            line_allocations_result = await self.db.execute(
                select(
                    CreditAllocation.invoice_line_id,
                    func.coalesce(func.sum(CreditAllocation.amount), 0),
                )
                .where(CreditAllocation.invoice_line_id.in_(line_ids))
                .group_by(CreditAllocation.invoice_line_id)
            )
            line_paid_map = {
                row[0]: Decimal(str(row[1])) for row in line_allocations_result.all()
            }

            explicit_line_total = round_money(
                sum(
                    (
                        line_paid_map.get(line.id, Decimal("0.00"))
                        for line in invoice.lines
                    ),
                    Decimal("0.00"),
                )
            )
            invoice_level_remainder = round_money(total_paid - explicit_line_total)
            remaining_capacities = {
                line.id: round_money(
                    max(
                        Decimal("0.00"),
                        line.net_amount - line_paid_map.get(line.id, Decimal("0.00")),
                    )
                )
                for line in invoice.lines
            }
            proportional_paid_map, _ = self._allocate_proportionally(
                max(Decimal("0.00"), invoice_level_remainder),
                remaining_capacities,
            )

            # Update each line with batch data
            for line in invoice.lines:
                line_paid = round_money(
                    line_paid_map.get(line.id, Decimal("0.00"))
                    + proportional_paid_map.get(line.id, Decimal("0.00"))
                )

                line.paid_amount = round_money(line_paid)
                line.remaining_amount = round_money(line.net_amount - line_paid)

    async def _sync_reservations_for_invoice(self, invoice_id: int, user_id: int) -> None:
        """Create/cancel reservations based on paid status of invoice lines."""
        reservation_service = ReservationService(self.db)
        await reservation_service.sync_for_invoice(invoice_id=invoice_id, user_id=user_id)

    async def _update_billing_account_balance_cache(self, billing_account_id: int) -> None:
        """Recalculate and mirror cached credit balance for a billing account."""
        payments_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.billing_account_id == billing_account_id,
                Payment.status == PaymentStatus.COMPLETED.value,
            )
        )
        total_payments = Decimal(str(payments_result.scalar() or 0))

        allocations_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.billing_account_id == billing_account_id
            )
        )
        total_allocated = Decimal(str(allocations_result.scalar() or 0))

        new_balance = round_money(total_payments - total_allocated)
        await self.db.execute(
            update(BillingAccount)
            .where(BillingAccount.id == billing_account_id)
            .values(cached_credit_balance=new_balance)
        )
        await self.db.execute(
            update(Student)
            .where(Student.billing_account_id == billing_account_id)
            .values(cached_credit_balance=new_balance)
        )

"""Atomic payment recipient corrections with a read-only, versioned preview."""

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import NotFoundError, ValidationError
from src.modules.billing_accounts.locking import lock_record_accounts
from src.modules.billing_accounts.models import BillingAccount
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.payments.models import (
    CreditAllocation,
    Payment,
    PaymentRefund,
    PaymentRefundSource,
)
from src.modules.payments.schemas import AllocationCreate
from src.modules.payments.service import PaymentService
from src.modules.payments.transfers.schedule import allocation_schedule
from src.modules.payments.transfers.schemas import (
    TransferInvoiceImpact,
    TransferParty,
    TransferPreview,
    TransferRequest,
)
from src.modules.students.models import Student
from src.shared.utils.money import round_money


@dataclass
class TransferContext:
    payment: Payment
    target: Student
    allocations: list[CreditAllocation]
    preview: TransferPreview


class PaymentTransferService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.payments = PaymentService(db)

    async def _party(self, student: Student, account_id: int) -> TransferParty:
        account = await self.db.get(BillingAccount, account_id)
        if account is None:
            raise ValidationError("Student has no billing account")
        return TransferParty(
            student_id=student.id,
            student_name=student.full_name,
            student_number=student.student_number,
            billing_account_id=account.id,
            account_number=account.account_number,
            account_name=account.display_name,
        )

    async def _credit(self, account_id: int) -> Decimal:
        # Calculate from the ledger, not the cached balance.
        total = Decimal("0")
        for model, sign in ((Payment, 1), (PaymentRefund, -1), (CreditAllocation, -1)):
            query = select(func.coalesce(func.sum(model.amount), 0)).where(
                model.billing_account_id == account_id
            )
            if model is Payment:
                query = query.where(Payment.status == "completed")
            total += Decimal(str(await self.db.scalar(query))) * sign
        return round_money(total)

    async def _context(self, payment_id: int, target_student_id: int) -> TransferContext:
        payment = await self.db.get(Payment, payment_id, populate_existing=True)
        target = await self.db.get(Student, target_student_id, populate_existing=True)
        if payment is None or target is None:
            raise NotFoundError("Payment or target student not found")
        if not payment.is_completed:
            raise ValidationError("Only completed payments can be transferred")
        if payment.student_id == target.id:
            raise ValidationError("Select a different student")
        if not target.billing_account_id:
            raise ValidationError("Target student has no billing account")
        source_student = await self.db.get(Student, payment.student_id)
        refunded = await self.db.scalar(
            select(PaymentRefund.id)
            .where(
                or_(
                    PaymentRefund.payment_id == payment.id,
                    PaymentRefund.id.in_(
                        select(PaymentRefundSource.refund_id).where(
                            PaymentRefundSource.payment_id == payment.id
                        )
                    ),
                )
            )
            .limit(1)
        )
        if refunded is not None:
            raise ValidationError(
                "This payment has a refund and cannot be transferred automatically"
            )
        allocations = list(
            (
                await self.db.scalars(
                    select(CreditAllocation)
                    .where(
                        CreditAllocation.source_payment_id == payment.id,
                        CreditAllocation.amount > 0,
                    )
                    .order_by(CreditAllocation.id)
                    .options(
                        selectinload(CreditAllocation.invoice).selectinload(Invoice.student),
                        selectinload(CreditAllocation.reversals),
                    )
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        same_account = payment.billing_account_id == target.billing_account_id
        if not same_account:
            if any(
                row.billing_account_id != payment.billing_account_id
                or row.invoice.billing_account_id != payment.billing_account_id
                or bool(row.reversals)
                for row in allocations
            ):
                raise ValidationError(
                    "Payment allocations have incompatible account or reversal history"
                )
        source_credit = await self._credit(payment.billing_account_id)
        target_credit = await self._credit(target.billing_account_id)
        released = round_money(sum((row.amount for row in allocations), Decimal("0")))
        if released > payment.amount:
            raise ValidationError("Allocations exceed the payment amount; review payment history")
        # Only the selected payment's unresolved portion needs attribution. Historical
        # allocations belonging to other receipts do not make a fully traced payment
        # ambiguous, and must never be rewritten as a prerequisite for its transfer.
        if not same_account and released < payment.amount:
            ambiguous = await self.db.scalar(
                select(CreditAllocation.id)
                .where(
                    CreditAllocation.billing_account_id == payment.billing_account_id,
                    CreditAllocation.source_payment_id.is_(None),
                    CreditAllocation.amount > 0,
                )
                .limit(1)
            )
            if ambiguous is not None:
                raise ValidationError(
                    "This payment is not fully linked to invoices, and some allocations "
                    "on the family account have no payment reference. Review this payment's "
                    "allocation history before transferring."
                )
        source_after = (
            source_credit
            if same_account
            else round_money(source_credit + released - payment.amount)
        )
        if source_after < 0:
            raise ValidationError(
                "The payment cannot be isolated without making the source credit negative"
            )
        removed = []
        new = []
        if not same_account:
            # Group invoice-level and line-level allocations for an accurate preview.
            invoice_totals: dict[int, Decimal] = {}
            for row in allocations:
                invoice_totals[row.invoice_id] = (
                    invoice_totals.get(row.invoice_id, Decimal("0")) + row.amount
                )
            invoices_by_id = {row.invoice_id: row.invoice for row in allocations}
            for invoice_id, amount in invoice_totals.items():
                invoice = invoices_by_id[invoice_id]
                removed.append(
                    TransferInvoiceImpact(
                        invoice_id=invoice.id,
                        invoice_number=invoice.invoice_number,
                        student_name=invoice.student.full_name,
                        amount=amount,
                        due_before=invoice.amount_due,
                        due_after=round_money(invoice.amount_due + amount),
                    )
                )
            candidates = list(
                (
                    await self.db.scalars(
                        select(Invoice)
                        .where(
                            Invoice.billing_account_id == target.billing_account_id,
                            Invoice.status.in_(
                                [InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value]
                            ),
                            Invoice.amount_due > 0,
                        )
                        .options(
                            selectinload(Invoice.lines).selectinload(InvoiceLine.kit),
                            selectinload(Invoice.lines).selectinload(InvoiceLine.item),
                            selectinload(Invoice.term),
                            selectinload(Invoice.student),
                        )
                        .execution_options(populate_existing=True)
                    )
                ).all()
            )
            if target_credit < 0:
                raise ValidationError(
                    "Target account has negative credit; reconcile it before transferring"
                )
            term = await self.payments._get_active_term()
            for invoice, amount in self.payments.plan_allocations(candidates, term, payment.amount):
                new.append(
                    TransferInvoiceImpact(
                        invoice_id=invoice.id,
                        invoice_number=invoice.invoice_number,
                        student_name=invoice.student.full_name,
                        amount=amount,
                        due_before=invoice.amount_due,
                        due_after=round_money(invoice.amount_due - amount),
                    )
                )
        allocated = sum((row.amount for row in new), Decimal("0"))
        preview = TransferPreview(
            payment_id=payment.id,
            payment_number=payment.payment_number,
            amount=payment.amount,
            source=await self._party(source_student, payment.billing_account_id),
            target=await self._party(target, target.billing_account_id),
            removed_allocations=removed,
            new_allocations=new,
            allocation_schedule=allocation_schedule(allocations, new),
            source_credit_before=source_credit,
            source_credit_after=source_after,
            target_credit_before=target_credit,
            target_credit_after=target_credit
            if same_account
            else round_money(target_credit + payment.amount - allocated),
        )
        version = (
            preview.model_dump_json()
            + str(payment.updated_at)
            + repr([(row.id, str(row.amount), row.invoice_line_id) for row in allocations])
        )
        preview.preview_token = hashlib.sha256(version.encode()).hexdigest()
        return TransferContext(payment, target, allocations, preview)

    async def preview(self, payment_id: int, target_student_id: int) -> TransferPreview:
        return (await self._context(payment_id, target_student_id)).preview

    async def transfer(
        self, payment_id: int, data: TransferRequest, user_id: int
    ) -> TransferPreview:
        try:
            await lock_record_accounts(
                self.db,
                [
                    (Payment, payment_id),
                    (Student, data.target_student_id),
                ],
            )
            context = await self._context(payment_id, data.target_student_id)
            preview = context.preview
            if data.preview_token != preview.preview_token:
                raise ValidationError(
                    "Payment or balances changed. Review a fresh transfer preview"
                )
            payment = context.payment
            same_account = preview.source.billing_account_id == preview.target.billing_account_id
            old_values = {
                "student_id": payment.student_id,
                "billing_account_id": payment.billing_account_id,
                "preferred_invoice_id": payment.preferred_invoice_id,
                "allocations": [
                    {
                        "id": row.id,
                        "invoice_id": row.invoice_id,
                        "invoice_line_id": row.invoice_line_id,
                        "amount": str(row.amount),
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in context.allocations
                ],
            }
            if not same_account:
                # This corrects a mistaken attribution; retain the old records in the
                # audit log rather than inventing a dated cash/refund event. Existing
                # reversal history is rejected above so deleting it is never necessary.
                for row in context.allocations:
                    await self.payments.delete_allocation(
                        row.id,
                        user_id,
                        reason=f"Payment transfer: {data.reason}",
                        commit=False,
                    )
            payment.student_id = context.target.id
            payment.billing_account_id = context.target.billing_account_id
            payment.preferred_invoice_id = None
            await self.db.flush()
            if not same_account:
                await self.payments._update_billing_account_balance_cache(
                    preview.source.billing_account_id
                )
                await self.payments._update_billing_account_balance_cache(
                    preview.target.billing_account_id
                )
                for part in preview.allocation_schedule:
                    await self.payments.allocate_manual(
                        AllocationCreate(
                            billing_account_id=payment.billing_account_id,
                            invoice_id=part.invoice_id,
                            amount=part.amount,
                        ),
                        user_id,
                        source_payment_id=payment.id,
                        allocation_created_at=part.created_at,
                        commit=False,
                    )
            await self.payments.audit.log(
                action="payment.transfer",
                entity_type="Payment",
                entity_id=payment.id,
                entity_identifier=payment.payment_number,
                user_id=user_id,
                old_values=old_values,
                new_values=preview.model_dump(mode="json"),
                comment=data.reason,
            )
            await self.db.commit()
            return preview
        except Exception:
            await self.db.rollback()
            raise

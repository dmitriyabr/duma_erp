"""Service for manual student and family withdrawal settlements."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.billing_accounts.service import BillingAccountService
from src.modules.invoices.models import (
    Invoice,
    InvoiceAdjustment,
    InvoiceAdjustmentType,
    InvoiceStatus,
)
from src.modules.payments.models import Payment, PaymentStatus
from src.modules.payments.schemas import BillingAccountRefundPreviewRequest
from src.modules.payments.service import PaymentService
from src.modules.students.models import Student, StudentStatus
from src.modules.withdrawals.models import (
    WithdrawalSettlement,
    WithdrawalSettlementLine,
    WithdrawalSettlementLineAction,
    WithdrawalSettlementStudent,
    WithdrawalSettlementStatus,
)
from src.modules.withdrawals.schemas import (
    BillingAccountWithdrawalSettlementCreate,
    BillingAccountWithdrawalSettlementPreviewRequest,
    WithdrawalInvoiceActionRequest,
    WithdrawalInvoiceImpact,
    WithdrawalSettlementCreate,
    WithdrawalSettlementPreview,
    WithdrawalSettlementPreviewRequest,
)
from src.shared.utils.money import round_money


class WithdrawalSettlementService:
    """Manage manual withdrawal settlements."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def preview_settlement(
        self,
        student_id: int,
        data: WithdrawalSettlementPreviewRequest,
    ) -> WithdrawalSettlementPreview:
        student = await self._get_student(student_id)
        billing_account_id = self._require_billing_account(student)
        return await self._preview_for_students(billing_account_id, [student], data)

    async def preview_billing_account_settlement(
        self,
        billing_account_id: int,
        data: BillingAccountWithdrawalSettlementPreviewRequest,
    ) -> WithdrawalSettlementPreview:
        students = await self._resolve_account_students(billing_account_id, data.student_ids)
        return await self._preview_for_students(billing_account_id, students, data)

    async def _preview_for_students(
        self,
        billing_account_id: int,
        students: list[Student],
        data: WithdrawalSettlementPreviewRequest | BillingAccountWithdrawalSettlementPreviewRequest,
    ) -> WithdrawalSettlementPreview:
        student_ids = [student.id for student in students]
        invoices = await self._load_students_invoices(student_ids)
        total_paid = await self._get_completed_payments_total(billing_account_id)
        current_debt = self._sum_current_debt(invoices)

        refund_preview = None
        refund_reopened_by_invoice: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
        refund_amount = Decimal("0.00")
        if data.refund is not None and round_money(data.refund.amount) > 0:
            refund_amount = round_money(data.refund.amount)
            refund_preview = await PaymentService(self.db).preview_billing_account_refund(
                billing_account_id,
                BillingAccountRefundPreviewRequest(
                    amount=refund_amount,
                    refund_date=data.refund.refund_date,
                    allocation_reversals=data.refund.allocation_reversals,
                ),
            )
            for impact in refund_preview.allocation_reversals:
                if impact.student_id not in student_ids:
                    raise ValidationError("Refund allocation reversals must belong to selected students")
                refund_reopened_by_invoice[impact.invoice_id] = round_money(
                    refund_reopened_by_invoice[impact.invoice_id] + impact.reversal_amount
                )

        action_impacts, write_off_total, cancelled_total = self._preview_invoice_actions(
            invoices,
            data.invoice_actions,
            refund_reopened_by_invoice,
        )
        remaining_debt = round_money(
            current_debt
            + round_money(sum(refund_reopened_by_invoice.values(), Decimal("0.00")))
            - write_off_total
            - cancelled_total
        )
        warnings: list[str] = []
        if remaining_debt > 0:
            warnings.append("Settlement leaves remaining collectible debt.")
        if refund_amount > 0 and data.refund is not None and not self._has_refund_proof(data.refund):
            warnings.append("Refund proof/reference is required before posting.")

        return WithdrawalSettlementPreview(
            student_id=students[0].id if len(students) == 1 else None,
            student_name=students[0].full_name if len(students) == 1 else None,
            student_ids=student_ids,
            student_names=[student.full_name for student in students],
            billing_account_id=billing_account_id,
            total_paid=total_paid,
            current_outstanding_debt=current_debt,
            retained_amount=round_money(data.retained_amount),
            deduction_amount=round_money(data.deduction_amount),
            write_off_amount=write_off_total,
            cancelled_amount=cancelled_total,
            refund_amount=refund_amount,
            remaining_collectible_debt_after=remaining_debt,
            invoice_impacts=action_impacts,
            refund_preview=refund_preview,
            warnings=warnings,
        )

    async def create_settlement(
        self,
        student_id: int,
        data: WithdrawalSettlementCreate,
        created_by_id: int,
    ) -> WithdrawalSettlement:
        student = await self._get_student(student_id)
        billing_account_id = self._require_billing_account(student)
        return await self._create_for_students(billing_account_id, [student], data, created_by_id)

    async def create_billing_account_settlement(
        self,
        billing_account_id: int,
        data: BillingAccountWithdrawalSettlementCreate,
        created_by_id: int,
    ) -> WithdrawalSettlement:
        students = await self._resolve_account_students(billing_account_id, data.student_ids)
        return await self._create_for_students(billing_account_id, students, data, created_by_id)

    async def _create_for_students(
        self,
        billing_account_id: int,
        students: list[Student],
        data: WithdrawalSettlementCreate | BillingAccountWithdrawalSettlementCreate,
        created_by_id: int,
    ) -> WithdrawalSettlement:
        inactive = [student.full_name for student in students if student.status == StudentStatus.INACTIVE.value]
        if inactive:
            raise ValidationError(f"Student is already inactive: {', '.join(inactive)}")

        preview = await self.preview_settlement(
            students[0].id,
            WithdrawalSettlementPreviewRequest(**data.model_dump(exclude={"student_ids"})),
        ) if len(students) == 1 else await self.preview_billing_account_settlement(
            billing_account_id,
            BillingAccountWithdrawalSettlementPreviewRequest(**data.model_dump()),
        )
        if data.refund is not None and round_money(data.refund.amount) > 0:
            if not self._has_refund_proof(data.refund):
                raise ValidationError("Reference, proof text or confirmation file is required for refund")

        number_gen = DocumentNumberGenerator(self.db)
        settlement = WithdrawalSettlement(
            settlement_number=await number_gen.generate("WDR"),
            student_id=students[0].id if len(students) == 1 else None,
            billing_account_id=billing_account_id,
            settlement_date=data.settlement_date,
            status=WithdrawalSettlementStatus.POSTED.value,
            retained_amount=round_money(data.retained_amount),
            deduction_amount=round_money(data.deduction_amount),
            write_off_amount=preview.write_off_amount,
            cancelled_amount=preview.cancelled_amount,
            refund_amount=preview.refund_amount,
            remaining_collectible_debt=preview.remaining_collectible_debt_after,
            reason=data.reason.strip(),
            notes=(data.notes or "").strip() or None,
            proof_attachment_id=data.proof_attachment_id,
            created_by_id=created_by_id,
            posted_at=datetime.now(timezone.utc),
        )
        self.db.add(settlement)
        await self.db.flush()

        status_before_by_student = {student.id: student.status for student in students}
        for student in students:
            self.db.add(
                WithdrawalSettlementStudent(
                    settlement_id=settlement.id,
                    student_id=student.id,
                    status_before=student.status,
                    status_after=StudentStatus.INACTIVE.value,
                )
            )

        refund = None
        if data.refund is not None and round_money(data.refund.amount) > 0:
            refund = await PaymentService(self.db).create_billing_account_refund(
                billing_account_id,
                data.refund,
                created_by_id,
                commit=False,
            )
            settlement.refund_id = refund.id
            await self.db.flush()

        invoices = await self._load_students_invoices([student.id for student in students])
        invoice_by_id = {invoice.id: invoice for invoice in invoices}

        for action in data.invoice_actions:
            self.db.add(
                WithdrawalSettlementLine(
                    settlement_id=settlement.id,
                    invoice_id=action.invoice_id,
                    invoice_line_id=action.invoice_line_id,
                    action=action.action.value,
                    amount=round_money(action.amount),
                    notes=(action.notes or "").strip() or None,
                )
            )
            if action.action == WithdrawalSettlementLineAction.CANCEL_UNPAID:
                await self._apply_cancel_unpaid(action, invoice_by_id, created_by_id)
            elif action.action == WithdrawalSettlementLineAction.WRITE_OFF:
                await self._apply_write_off(action, invoice_by_id, settlement.id, created_by_id, data.reason)

        for student in students:
            student.status = StudentStatus.INACTIVE.value

        await self.audit.log(
            action="student.withdrawal_settlement",
            entity_type="WithdrawalSettlement",
            entity_id=settlement.id,
            entity_identifier=settlement.settlement_number,
            user_id=created_by_id,
            old_values={"student_statuses": status_before_by_student},
            new_values={
                "student_ids": [student.id for student in students],
                "student_status": StudentStatus.INACTIVE.value,
                "refund_id": refund.id if refund else None,
                "write_off_amount": str(settlement.write_off_amount),
                "cancelled_amount": str(settlement.cancelled_amount),
                "refund_amount": str(settlement.refund_amount),
                "remaining_collectible_debt": str(settlement.remaining_collectible_debt),
            },
            comment=data.reason,
        )

        await BillingAccountService(self.db).sync_cached_balance(billing_account_id)
        await self.db.commit()
        return await self.get_settlement_by_id(settlement.id)

    async def list_student_settlements(self, student_id: int) -> list[WithdrawalSettlement]:
        await self._get_student(student_id)
        result = await self.db.execute(
            self._settlement_query()
            .where(
                or_(
                    WithdrawalSettlement.student_id == student_id,
                    exists().where(
                        WithdrawalSettlementStudent.settlement_id == WithdrawalSettlement.id,
                        WithdrawalSettlementStudent.student_id == student_id,
                    ),
                )
            )
            .order_by(WithdrawalSettlement.settlement_date.desc(), WithdrawalSettlement.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def list_billing_account_settlements(
        self, billing_account_id: int
    ) -> list[WithdrawalSettlement]:
        result = await self.db.execute(
            self._settlement_query()
            .where(WithdrawalSettlement.billing_account_id == billing_account_id)
            .order_by(WithdrawalSettlement.settlement_date.desc(), WithdrawalSettlement.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def get_settlement_by_id(self, settlement_id: int) -> WithdrawalSettlement:
        result = await self.db.execute(
            self._settlement_query().where(WithdrawalSettlement.id == settlement_id)
        )
        settlement = result.scalar_one_or_none()
        if settlement is None:
            raise NotFoundError(f"Withdrawal settlement with id {settlement_id} not found")
        return settlement

    def _settlement_query(self):
        return select(WithdrawalSettlement).options(
            selectinload(WithdrawalSettlement.student),
            selectinload(WithdrawalSettlement.students).selectinload(
                WithdrawalSettlementStudent.student
            ),
            selectinload(WithdrawalSettlement.refund),
            selectinload(WithdrawalSettlement.lines).selectinload(WithdrawalSettlementLine.invoice),
            selectinload(WithdrawalSettlement.invoice_adjustments).selectinload(
                InvoiceAdjustment.invoice
            ),
        )

    async def _get_student(self, student_id: int) -> Student:
        result = await self.db.execute(
            select(Student).where(Student.id == student_id).options(selectinload(Student.billing_account))
        )
        student = result.scalar_one_or_none()
        if student is None:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    def _require_billing_account(self, student: Student) -> int:
        if student.billing_account_id is None:
            raise ValidationError("Student has no billing account")
        return int(student.billing_account_id)

    async def _resolve_account_students(
        self,
        billing_account_id: int,
        student_ids: list[int],
    ) -> list[Student]:
        query = (
            select(Student)
            .where(Student.billing_account_id == billing_account_id)
            .options(selectinload(Student.billing_account))
            .order_by(Student.last_name, Student.first_name, Student.id)
        )
        if student_ids:
            query = query.where(Student.id.in_(student_ids))
        else:
            query = query.where(Student.status == StudentStatus.ACTIVE.value)

        result = await self.db.execute(query)
        students = list(result.scalars().unique().all())
        if not students:
            raise ValidationError("No students selected for withdrawal settlement")

        requested_ids = set(student_ids)
        found_ids = {student.id for student in students}
        missing = requested_ids - found_ids
        if missing:
            raise ValidationError("Selected students must belong to this billing account")

        return students

    async def _load_student_invoices(self, student_id: int) -> list[Invoice]:
        return await self._load_students_invoices([student_id])

    async def _load_students_invoices(self, student_ids: list[int]) -> list[Invoice]:
        if not student_ids:
            return []
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.student_id.in_(student_ids))
            .options(
                selectinload(Invoice.student),
                selectinload(Invoice.lines),
            )
            .order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        )
        return list(result.scalars().unique().all())

    async def _get_completed_payments_total(self, billing_account_id: int) -> Decimal:
        result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.billing_account_id == billing_account_id,
                Payment.status == PaymentStatus.COMPLETED.value,
            )
        )
        return round_money(Decimal(str(result.scalar() or 0)))

    def _sum_current_debt(self, invoices: list[Invoice]) -> Decimal:
        included = {InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value}
        return round_money(
            sum(
                (
                    round_money(sum((line.remaining_amount for line in invoice.lines), Decimal("0.00")))
                    for invoice in invoices
                    if invoice.status in included
                ),
                Decimal("0.00"),
            )
        )

    def _preview_invoice_actions(
        self,
        invoices: list[Invoice],
        actions: list[WithdrawalInvoiceActionRequest],
        refund_reopened_by_invoice: dict[int, Decimal],
    ) -> tuple[list[WithdrawalInvoiceImpact], Decimal, Decimal]:
        invoice_by_id = {invoice.id: invoice for invoice in invoices}
        write_off_total = Decimal("0.00")
        cancelled_total = Decimal("0.00")
        impacts: list[WithdrawalInvoiceImpact] = []
        consumed_by_invoice: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))

        for action in actions:
            if action.action in (
                WithdrawalSettlementLineAction.DEDUCTION,
                WithdrawalSettlementLineAction.KEEP_CHARGED,
                WithdrawalSettlementLineAction.REFUND_ALLOCATION,
            ):
                continue
            invoice = invoice_by_id.get(int(action.invoice_id or 0))
            if invoice is None:
                raise ValidationError("Selected invoice does not belong to this student")
            current_due = self._invoice_current_due(invoice)
            basis_due = round_money(
                current_due
                + refund_reopened_by_invoice.get(invoice.id, Decimal("0.00"))
                - consumed_by_invoice[invoice.id]
            )
            amount = round_money(action.amount)
            if amount > basis_due:
                raise ValidationError("Settlement action exceeds invoice amount due")

            if action.action == WithdrawalSettlementLineAction.CANCEL_UNPAID:
                if round_money(invoice.paid_total) > 0:
                    raise ValidationError("Only unpaid invoices can be cancelled")
                status_after = InvoiceStatus.CANCELLED.value
                cancelled_total = round_money(cancelled_total + amount)
            elif action.action == WithdrawalSettlementLineAction.WRITE_OFF:
                status_after = InvoiceStatus.PAID.value if amount == basis_due else invoice.status
                write_off_total = round_money(write_off_total + amount)
            else:
                continue

            consumed_by_invoice[invoice.id] = round_money(consumed_by_invoice[invoice.id] + amount)
            impacts.append(
                WithdrawalInvoiceImpact(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    student_id=invoice.student_id,
                    student_name=invoice.student.full_name if invoice.student else None,
                    invoice_type=invoice.invoice_type,
                    status_before=invoice.status,
                    status_after=status_after,
                    action=action.action.value,
                    amount=amount,
                    amount_due_before=current_due,
                    amount_due_after=round_money(basis_due - amount),
                    notes=action.notes,
                )
            )
        return impacts, write_off_total, cancelled_total

    def _invoice_current_due(self, invoice: Invoice) -> Decimal:
        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
            return Decimal("0.00")
        return round_money(sum((line.remaining_amount for line in invoice.lines), Decimal("0.00")))

    async def _apply_cancel_unpaid(
        self,
        action: WithdrawalInvoiceActionRequest,
        invoice_by_id: dict[int, Invoice],
        user_id: int,
    ) -> None:
        invoice = invoice_by_id.get(int(action.invoice_id or 0))
        if invoice is None:
            raise ValidationError("Selected invoice does not belong to this student")
        if round_money(invoice.paid_total) > 0:
            raise ValidationError("Only unpaid invoices can be cancelled")
        if invoice.status not in (InvoiceStatus.DRAFT.value, InvoiceStatus.ISSUED.value):
            raise ValidationError(f"Cannot cancel invoice with status '{invoice.status}'")
        old_status = invoice.status
        invoice.status = InvoiceStatus.CANCELLED.value
        await self.audit.log(
            action="invoice.cancel",
            entity_type="Invoice",
            entity_id=invoice.id,
            user_id=user_id,
            old_values={"status": old_status},
            new_values={"status": InvoiceStatus.CANCELLED.value},
            comment=action.notes or "Withdrawal settlement",
        )

    async def _apply_write_off(
        self,
        action: WithdrawalInvoiceActionRequest,
        invoice_by_id: dict[int, Invoice],
        settlement_id: int,
        user_id: int,
        reason: str,
    ) -> None:
        invoice = invoice_by_id.get(int(action.invoice_id or 0))
        if invoice is None:
            raise ValidationError("Selected invoice does not belong to this student")
        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
            raise ValidationError("Cannot write off cancelled or void invoice")
        remaining = round_money(action.amount)
        lines = [line for line in invoice.lines if line.remaining_amount > 0]
        if not lines:
            raise ValidationError("Invoice has no amount due to write off")
        if remaining > round_money(sum((line.remaining_amount for line in lines), Decimal("0.00"))):
            raise ValidationError("Write-off exceeds invoice amount due")

        number_gen = DocumentNumberGenerator(self.db)
        for line in lines:
            if remaining <= 0:
                break
            line_amount = min(remaining, round_money(line.remaining_amount))
            adjustment = InvoiceAdjustment(
                adjustment_number=await number_gen.generate("ADJ"),
                invoice_id=invoice.id,
                invoice_line_id=line.id,
                settlement_id=settlement_id,
                adjustment_type=InvoiceAdjustmentType.WITHDRAWAL_WRITE_OFF.value,
                amount=line_amount,
                reason=reason.strip(),
                notes=(action.notes or "").strip() or None,
                created_by_id=user_id,
            )
            self.db.add(adjustment)
            line.adjustment_amount = round_money(line.adjustment_amount + line_amount)
            line.remaining_amount = round_money(line.net_amount - line.paid_amount - line.adjustment_amount)
            remaining = round_money(remaining - line_amount)

        self._recalculate_invoice_after_adjustment(invoice)

    def _recalculate_invoice_after_adjustment(self, invoice: Invoice) -> None:
        invoice.adjustment_total = round_money(
            sum((line.adjustment_amount for line in invoice.lines), Decimal("0.00"))
        )
        invoice.paid_total = round_money(sum((line.paid_amount for line in invoice.lines), Decimal("0.00")))
        invoice.amount_due = round_money(invoice.total - invoice.paid_total - invoice.adjustment_total)
        if invoice.status not in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value, InvoiceStatus.DRAFT.value):
            if invoice.amount_due <= 0:
                invoice.status = InvoiceStatus.PAID.value
            elif invoice.paid_total > 0:
                invoice.status = InvoiceStatus.PARTIALLY_PAID.value
            else:
                invoice.status = InvoiceStatus.ISSUED.value

    def _has_refund_proof(self, refund) -> bool:
        return bool(
            (refund.reference_number or "").strip()
            or (refund.proof_text or "").strip()
            or refund.proof_attachment_id is not None
        )

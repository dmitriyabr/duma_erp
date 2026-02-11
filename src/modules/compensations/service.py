"""Service for expense claims."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.documents.number_generator import get_document_number
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.compensations.models import (
    CompensationPayout,
    EmployeeBalance,
    ExpenseClaim,
    ExpenseClaimStatus,
    PayoutAllocation,
)
from src.modules.compensations.schemas import (
    CompensationPayoutCreate,
    ExpenseClaimCreate,
    ExpenseClaimUpdate,
    EmployeeBalanceResponse,
    EmployeeClaimTotalsResponse,
)
from src.shared.utils.money import round_money
from src.modules.procurement.models import (
    PaymentPurpose,
    ProcurementPayment,
    ProcurementPaymentMethod,
    ProcurementPaymentStatus,
)


class ExpenseClaimService:
    """Expense claim service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_transaction_fee_purpose(self) -> PaymentPurpose:
        purpose = await self.db.scalar(
            select(PaymentPurpose).where(PaymentPurpose.name.ilike("Transaction Fees"))
        )
        if purpose:
            # Ensure correct type (backwards compatible if it existed before purpose_type).
            if getattr(purpose, "purpose_type", None) != "fee":
                purpose.purpose_type = "fee"
                await self.db.flush()
            return purpose

        purpose = PaymentPurpose(name="Transaction Fees", is_active=True, purpose_type="fee")
        self.db.add(purpose)
        await self.db.flush()
        return purpose

    async def create_from_payment(self, payment: ProcurementPayment) -> ExpenseClaim:
        """Create expense claim from procurement payment."""
        claim_number = await get_document_number(self.db, "CLM")
        claim = ExpenseClaim(
            claim_number=claim_number,
            payment_id=payment.id,
            fee_payment_id=None,
            employee_id=payment.employee_paid_id,
            purpose_id=payment.purpose_id,
            amount=payment.amount,
            fee_amount=Decimal("0.00"),
            description=payment.reference_number or f"Payment {payment.payment_number}",
            expense_date=payment.payment_date,
            status=ExpenseClaimStatus.PENDING_APPROVAL.value,
            paid_amount=Decimal("0.00"),
            remaining_amount=payment.amount,
            auto_created_from_payment=True,
            related_procurement_payment_id=payment.id,
        )
        self.db.add(claim)
        await self.db.flush()
        return claim

    async def create_out_of_pocket_claim(
        self,
        data: ExpenseClaimCreate,
        *,
        employee_id: int,
        created_by_id: int,
    ) -> ExpenseClaim:
        """Create an out-of-pocket expense claim (creates a procurement payment under the hood)."""
        # Proof is always required (we don't support "draft" claims).
        if not data.proof_text and not data.proof_attachment_id:
            raise ValidationError("Proof is required: provide proof_text or proof_attachment_id")

        # Validate purpose exists (shared catalog for procurement + claims).
        purpose = await self.db.scalar(select(PaymentPurpose).where(PaymentPurpose.id == data.purpose_id))
        if not purpose:
            raise ValidationError("Invalid purpose_id")

        payment_number = await get_document_number(self.db, "PPAY")
        payment = ProcurementPayment(
            payment_number=payment_number,
            po_id=None,
            purpose_id=data.purpose_id,
            payee_name=data.payee_name,
            payment_date=data.expense_date,
            amount=data.amount,
            payment_method=ProcurementPaymentMethod.EMPLOYEE.value,
            reference_number=None,
            proof_text=data.proof_text,
            proof_attachment_id=data.proof_attachment_id,
            company_paid=False,
            employee_paid_id=employee_id,
            status=ProcurementPaymentStatus.POSTED.value,
            created_by_id=created_by_id,
        )
        self.db.add(payment)
        await self.db.flush()

        fee_amount = Decimal(str(data.fee_amount)) if data.fee_amount and data.fee_amount > 0 else Decimal("0.00")
        fee_payment_id: int | None = None
        if fee_amount > 0:
            fee_purpose = await self._get_or_create_transaction_fee_purpose()

            fee_payment_number = await get_document_number(self.db, "PPAY")
            fee_payment = ProcurementPayment(
                payment_number=fee_payment_number,
                po_id=None,
                purpose_id=fee_purpose.id,
                payee_name="M-Pesa",
                payment_date=data.expense_date,
                amount=fee_amount,
                payment_method=ProcurementPaymentMethod.EMPLOYEE.value,
                reference_number=None,
                proof_text=data.fee_proof_text,
                proof_attachment_id=data.fee_proof_attachment_id,
                company_paid=False,
                employee_paid_id=employee_id,
                status=ProcurementPaymentStatus.POSTED.value,
                created_by_id=created_by_id,
            )
            self.db.add(fee_payment)
            await self.db.flush()
            fee_payment_id = fee_payment.id

        claim_number = await get_document_number(self.db, "CLM")
        status = ExpenseClaimStatus.PENDING_APPROVAL.value
        total_amount = Decimal(str(data.amount)) + fee_amount
        claim = ExpenseClaim(
            claim_number=claim_number,
            payment_id=payment.id,
            fee_payment_id=fee_payment_id,
            employee_id=employee_id,
            purpose_id=data.purpose_id,
            amount=total_amount,
            fee_amount=fee_amount,
            description=data.description,
            expense_date=data.expense_date,
            status=status,
            paid_amount=Decimal("0.00"),
            remaining_amount=total_amount,
            auto_created_from_payment=False,
            related_procurement_payment_id=payment.id,
        )
        self.db.add(claim)
        await self.db.commit()
        return await self.get_claim_by_id(claim.id)

    async def update_out_of_pocket_claim(
        self,
        claim_id: int,
        data: ExpenseClaimUpdate,
        *,
        employee_id: int,
    ) -> ExpenseClaim:
        """Update an out-of-pocket claim. Only allowed in draft and only for the owner (or admin via router)."""
        claim = await self.get_claim_by_id(claim_id)
        if claim.employee_id != employee_id:
            raise ValidationError("Cannot update claim for another employee")
        if claim.status != ExpenseClaimStatus.DRAFT.value:
            raise ValidationError("Only draft claims can be updated")
        if not claim.payment_id:
            raise ValidationError("Cannot update claim without linked payment")

        update = data.model_dump(exclude_unset=True)
        submit = update.pop("submit", None)

        # Extract fee-related updates (these live on the optional fee payment, not on the claim row).
        fee_amount = None
        if "fee_amount" in update:
            fee_amount = Decimal(str(update.pop("fee_amount") or 0))
        fee_proof_text = update.pop("fee_proof_text", None) if "fee_proof_text" in update else None
        fee_proof_attachment_id = (
            update.pop("fee_proof_attachment_id", None) if "fee_proof_attachment_id" in update else None
        )

        # Keep linked procurement payment in sync for expense-related fields.
        payment = claim.payment
        if payment is None:
            payment = await self.db.scalar(select(ProcurementPayment).where(ProcurementPayment.id == claim.payment_id))
        if payment is None:
            raise ValidationError("Linked payment not found")

        # Validate purpose exists (shared catalog for procurement + claims).
        if "purpose_id" in update and update["purpose_id"] is not None:
            purpose = await self.db.scalar(select(PaymentPurpose).where(PaymentPurpose.id == update["purpose_id"]))
            if not purpose:
                raise ValidationError("Invalid purpose_id")
            claim.purpose_id = update["purpose_id"]
            payment.purpose_id = update["purpose_id"]

        if "description" in update and update["description"] is not None:
            claim.description = update["description"]

        if "payee_name" in update:
            payment.payee_name = update["payee_name"]

        if "expense_date" in update and update["expense_date"] is not None:
            claim.expense_date = update["expense_date"]
            payment.payment_date = update["expense_date"]

        if "amount" in update and update["amount"] is not None:
            payment.amount = update["amount"]

        if "proof_text" in update:
            payment.proof_text = update["proof_text"]
        if "proof_attachment_id" in update:
            payment.proof_attachment_id = update["proof_attachment_id"]

        # Fee payment sync (optional)
        if fee_amount is not None:
            if fee_amount < 0:
                raise ValidationError("fee_amount must be >= 0")

            if fee_amount == 0:
                # Remove fee from claim; cancel fee payment if exists.
                if claim.fee_payment_id:
                    from src.modules.procurement.service import ProcurementPaymentService

                    await ProcurementPaymentService(self.db).cancel_payment(
                        claim.fee_payment_id,
                        reason="Fee removed",
                        cancelled_by_id=employee_id,
                    )
                claim.fee_payment_id = None
                claim.fee_amount = Decimal("0.00")
            else:
                # Ensure fee proof exists if fee is present.
                if not fee_proof_text and not fee_proof_attachment_id:
                    fee_payment = claim.fee_payment
                    if fee_payment is None and claim.fee_payment_id:
                        fee_payment = await self.db.scalar(
                            select(ProcurementPayment).where(ProcurementPayment.id == claim.fee_payment_id)
                        )
                    if not fee_payment or (not fee_payment.proof_text and not fee_payment.proof_attachment_id):
                        raise ValidationError("Fee proof is required: provide fee_proof_text or fee_proof_attachment_id")

                fee_purpose = await self._get_or_create_transaction_fee_purpose()

                fee_payment = claim.fee_payment
                if fee_payment is None and claim.fee_payment_id:
                    fee_payment = await self.db.scalar(
                        select(ProcurementPayment).where(ProcurementPayment.id == claim.fee_payment_id)
                    )

                if fee_payment is None:
                    fee_payment_number = await get_document_number(self.db, "PPAY")
                    fee_payment = ProcurementPayment(
                        payment_number=fee_payment_number,
                        po_id=None,
                        purpose_id=fee_purpose.id,
                        payee_name="M-Pesa",
                        payment_date=payment.payment_date,
                        amount=fee_amount,
                        payment_method=ProcurementPaymentMethod.EMPLOYEE.value,
                        reference_number=None,
                        proof_text=fee_proof_text,
                        proof_attachment_id=fee_proof_attachment_id,
                        company_paid=False,
                        employee_paid_id=employee_id,
                        status=ProcurementPaymentStatus.POSTED.value,
                        created_by_id=employee_id,
                    )
                    self.db.add(fee_payment)
                    await self.db.flush()
                    claim.fee_payment_id = fee_payment.id
                else:
                    fee_payment.purpose_id = fee_purpose.id
                    fee_payment.amount = fee_amount
                    if fee_proof_text is not None:
                        fee_payment.proof_text = fee_proof_text
                    if fee_proof_attachment_id is not None:
                        fee_payment.proof_attachment_id = fee_proof_attachment_id

                claim.fee_amount = fee_amount

        # Recalculate claim total (draft only; nothing allocated yet).
        claim_total = Decimal(str(payment.amount)) + Decimal(str(claim.fee_amount or 0))
        claim.amount = claim_total
        claim.paid_amount = Decimal("0.00")
        claim.remaining_amount = claim_total

        if submit is True:
            # Validate proof on submit (schema also validates, but keep defensive).
            if not payment.proof_text and not payment.proof_attachment_id:
                raise ValidationError("Proof is required: provide proof_text or proof_attachment_id")
            if claim.fee_amount and claim.fee_amount > 0:
                fee_payment = claim.fee_payment
                if fee_payment is None and claim.fee_payment_id:
                    fee_payment = await self.db.scalar(
                        select(ProcurementPayment).where(ProcurementPayment.id == claim.fee_payment_id)
                    )
                if not fee_payment or (not fee_payment.proof_text and not fee_payment.proof_attachment_id):
                    raise ValidationError("Fee proof is required: provide fee_proof_text or fee_proof_attachment_id")
            claim.status = ExpenseClaimStatus.PENDING_APPROVAL.value

        await self.db.commit()
        return await self.get_claim_by_id(claim_id)

    async def submit_claim(self, claim_id: int, *, employee_id: int) -> ExpenseClaim:
        """Submit a draft claim for approval."""
        claim = await self.get_claim_by_id(claim_id)
        if claim.employee_id != employee_id:
            raise ValidationError("Cannot submit claim for another employee")
        if claim.status != ExpenseClaimStatus.DRAFT.value:
            raise ValidationError("Only draft claims can be submitted")
        payment = claim.payment
        if payment is None:
            payment = await self.db.scalar(select(ProcurementPayment).where(ProcurementPayment.id == claim.payment_id))
        if not payment or (not payment.proof_text and not payment.proof_attachment_id):
            raise ValidationError("Proof is required: provide proof_text or proof_attachment_id")
        if claim.fee_amount and claim.fee_amount > 0:
            fee_payment = claim.fee_payment
            if fee_payment is None and claim.fee_payment_id:
                fee_payment = await self.db.scalar(
                    select(ProcurementPayment).where(ProcurementPayment.id == claim.fee_payment_id)
                )
            if not fee_payment or (not fee_payment.proof_text and not fee_payment.proof_attachment_id):
                raise ValidationError("Fee proof is required: provide fee_proof_text or fee_proof_attachment_id")
        claim.status = ExpenseClaimStatus.PENDING_APPROVAL.value
        await self.db.commit()
        return await self.get_claim_by_id(claim_id)

    async def approve_claim(
        self,
        claim_id: int,
        approve: bool,
        reason: str | None = None,
        *,
        acted_by_id: int,
    ) -> ExpenseClaim:
        """Approve or reject an expense claim."""
        claim = await self.get_claim_by_id(claim_id)
        if claim.status not in (
            ExpenseClaimStatus.PENDING_APPROVAL.value,
            ExpenseClaimStatus.DRAFT.value,
        ):
            raise ValidationError("Claim is not pending approval")

        if approve:
            claim.status = ExpenseClaimStatus.APPROVED.value
            claim.rejection_reason = None
            # Ensure remaining_amount reflects the claim amount (defensive).
            if claim.remaining_amount <= 0:
                claim.remaining_amount = Decimal(str(claim.amount))
        else:
            claim.status = ExpenseClaimStatus.REJECTED.value
            claim.rejection_reason = reason.strip() if reason else None
            # Rejected claim means no obligation remains.
            claim.paid_amount = Decimal("0.00")
            claim.remaining_amount = Decimal("0.00")
            # Cancel the linked procurement payment so it doesn't count as an expense.
            if claim.payment_id:
                # Use ProcurementPaymentService so PO totals are adjusted if this payment is tied to a PO.
                from src.modules.procurement.service import ProcurementPaymentService

                await ProcurementPaymentService(self.db).cancel_payment(
                    claim.payment_id,
                    reason=claim.rejection_reason or "Rejected",
                    cancelled_by_id=acted_by_id,
                )
            if getattr(claim, "fee_payment_id", None):
                from src.modules.procurement.service import ProcurementPaymentService

                await ProcurementPaymentService(self.db).cancel_payment(
                    claim.fee_payment_id,
                    reason=claim.rejection_reason or "Rejected",
                    cancelled_by_id=acted_by_id,
                )
        await self.db.commit()
        return await self.get_claim_by_id(claim_id)

    async def get_claim_by_id(self, claim_id: int) -> ExpenseClaim:
        result = await self.db.execute(
            select(ExpenseClaim)
            .where(ExpenseClaim.id == claim_id)
            .options(
                selectinload(ExpenseClaim.payment),
                selectinload(ExpenseClaim.fee_payment),
                selectinload(ExpenseClaim.employee),
                selectinload(ExpenseClaim.purpose),
            )
        )
        claim = result.scalar_one_or_none()
        if not claim:
            raise NotFoundError(f"Expense claim {claim_id} not found")
        return claim

    async def list_claims(
        self,
        employee_id: int | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[ExpenseClaim], int]:
        query = select(ExpenseClaim).options(
            selectinload(ExpenseClaim.payment),
            selectinload(ExpenseClaim.fee_payment),
            selectinload(ExpenseClaim.employee),
            selectinload(ExpenseClaim.purpose),
        )
        if employee_id:
            query = query.where(ExpenseClaim.employee_id == employee_id)
        if status:
            query = query.where(ExpenseClaim.status == status)
        if date_from:
            query = query.where(ExpenseClaim.expense_date >= date_from)
        if date_to:
            query = query.where(ExpenseClaim.expense_date <= date_to)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(ExpenseClaim.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total or 0


class PayoutService:
    """Service for payouts and allocations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payout(self, data: CompensationPayoutCreate) -> CompensationPayout:
        payout_number = await get_document_number(self.db, "PAY")
        payout = CompensationPayout(
            payout_number=payout_number,
            employee_id=data.employee_id,
            payout_date=data.payout_date,
            amount=data.amount,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            proof_text=data.proof_text,
            proof_attachment_id=data.proof_attachment_id,
        )
        self.db.add(payout)
        await self.db.flush()

        await self._allocate_payout(payout)

        await self._recalculate_employee_balance(data.employee_id)
        await self.db.commit()
        return await self.get_payout_by_id(payout.id)

    async def _allocate_payout(
        self, payout: CompensationPayout
    ) -> list[PayoutAllocation]:
        remaining = payout.amount
        allocations: list[PayoutAllocation] = []

        result = await self.db.execute(
            select(ExpenseClaim)
            .where(
                ExpenseClaim.employee_id == payout.employee_id,
                ExpenseClaim.status.in_(
                    [
                        ExpenseClaimStatus.APPROVED.value,
                        ExpenseClaimStatus.PARTIALLY_PAID.value,
                    ]
                ),
                ExpenseClaim.remaining_amount > 0,
            )
            .order_by(ExpenseClaim.expense_date.asc(), ExpenseClaim.id.asc())
        )
        claims = list(result.scalars().all())

        for claim in claims:
            if remaining <= 0:
                break
            to_allocate = min(remaining, claim.remaining_amount)
            allocation = PayoutAllocation(
                payout_id=payout.id,
                claim_id=claim.id,
                allocated_amount=to_allocate,
            )
            self.db.add(allocation)
            allocations.append(allocation)

            claim.paid_amount += to_allocate
            claim.remaining_amount -= to_allocate
            if claim.remaining_amount <= 0:
                claim.status = ExpenseClaimStatus.PAID.value
            else:
                claim.status = ExpenseClaimStatus.PARTIALLY_PAID.value

            remaining -= to_allocate

        return allocations

    async def _recalculate_employee_balance(self, employee_id: int) -> EmployeeBalance:
        approved_total = await self.db.scalar(
            select(func.coalesce(func.sum(ExpenseClaim.amount), 0)).where(
                ExpenseClaim.employee_id == employee_id,
                ExpenseClaim.status.in_(
                    [
                        ExpenseClaimStatus.APPROVED.value,
                        ExpenseClaimStatus.PARTIALLY_PAID.value,
                        ExpenseClaimStatus.PAID.value,
                    ]
                ),
            )
        )
        paid_total = await self.db.scalar(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.employee_id == employee_id
            )
        )

        balance = Decimal(approved_total) - Decimal(paid_total)

        result = await self.db.execute(
            select(EmployeeBalance).where(EmployeeBalance.employee_id == employee_id)
        )
        employee_balance = result.scalar_one_or_none()
        if not employee_balance:
            employee_balance = EmployeeBalance(
                employee_id=employee_id,
                total_approved=Decimal(approved_total),
                total_paid=Decimal(paid_total),
                balance=Decimal(balance),
            )
            self.db.add(employee_balance)
            await self.db.flush()
            return employee_balance

        employee_balance.total_approved = Decimal(approved_total)
        employee_balance.total_paid = Decimal(paid_total)
        employee_balance.balance = Decimal(balance)
        return employee_balance

    async def get_payout_by_id(self, payout_id: int) -> CompensationPayout:
        result = await self.db.execute(
            select(CompensationPayout)
            .where(CompensationPayout.id == payout_id)
            .options(selectinload(CompensationPayout.allocations))
        )
        payout = result.scalar_one_or_none()
        if not payout:
            raise NotFoundError(f"Payout {payout_id} not found")
        return payout

    async def list_payouts(
        self,
        employee_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[CompensationPayout], int]:
        query = select(CompensationPayout).options(
            selectinload(CompensationPayout.allocations)
        )
        if employee_id:
            query = query.where(CompensationPayout.employee_id == employee_id)
        if date_from:
            query = query.where(CompensationPayout.payout_date >= date_from)
        if date_to:
            query = query.where(CompensationPayout.payout_date <= date_to)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(CompensationPayout.payout_date.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total or 0

    async def get_employee_balance(self, employee_id: int) -> EmployeeBalance:
        """Return employee balance. Always recalculates from claims and payouts so approved claims are reflected."""
        employee_balance = await self._recalculate_employee_balance(employee_id)
        await self.db.commit()
        await self.db.refresh(employee_balance)
        return employee_balance

    async def get_employee_balances_batch(
        self, employee_ids: list[int]
    ) -> list[EmployeeBalanceResponse]:
        """Return balances for multiple employees in one go (no DB persist, computed only)."""
        if not employee_ids:
            return []

        approved_statuses = [
            ExpenseClaimStatus.APPROVED.value,
            ExpenseClaimStatus.PARTIALLY_PAID.value,
            ExpenseClaimStatus.PAID.value,
        ]
        approved_result = await self.db.execute(
            select(
                ExpenseClaim.employee_id,
                func.coalesce(func.sum(ExpenseClaim.amount), 0),
            )
            .where(
                ExpenseClaim.employee_id.in_(employee_ids),
                ExpenseClaim.status.in_(approved_statuses),
            )
            .group_by(ExpenseClaim.employee_id)
        )
        approved_by_emp = {row[0]: Decimal(str(row[1])) for row in approved_result.all()}

        paid_result = await self.db.execute(
            select(
                CompensationPayout.employee_id,
                func.coalesce(func.sum(CompensationPayout.amount), 0),
            )
            .where(CompensationPayout.employee_id.in_(employee_ids))
            .group_by(CompensationPayout.employee_id)
        )
        paid_by_emp = {row[0]: Decimal(str(row[1])) for row in paid_result.all()}

        return [
            EmployeeBalanceResponse(
                employee_id=eid,
                total_approved=round_money(approved_by_emp.get(eid, Decimal("0"))),
                total_paid=round_money(paid_by_emp.get(eid, Decimal("0"))),
                balance=round_money(
                    approved_by_emp.get(eid, Decimal("0")) - paid_by_emp.get(eid, Decimal("0"))
                ),
            )
            for eid in employee_ids
        ]

    async def get_employee_claim_totals(self, employee_id: int) -> EmployeeClaimTotalsResponse:
        """Return claimant-friendly totals (includes pending approval)."""
        submitted_statuses = [
            ExpenseClaimStatus.PENDING_APPROVAL.value,
            ExpenseClaimStatus.APPROVED.value,
            ExpenseClaimStatus.REJECTED.value,
            ExpenseClaimStatus.PARTIALLY_PAID.value,
            ExpenseClaimStatus.PAID.value,
        ]

        rows = await self.db.execute(
            select(
                ExpenseClaim.status,
                func.count(ExpenseClaim.id),
                func.coalesce(func.sum(ExpenseClaim.amount), 0),
            )
            .where(
                ExpenseClaim.employee_id == employee_id,
                ExpenseClaim.status.in_(submitted_statuses),
            )
            .group_by(ExpenseClaim.status)
        )
        by_status = {row[0]: (int(row[1]), Decimal(str(row[2]))) for row in rows.all()}

        count_submitted = sum(count for count, _ in by_status.values())
        total_submitted = sum(total for _, total in by_status.values())

        count_pending, total_pending = by_status.get(
            ExpenseClaimStatus.PENDING_APPROVAL.value, (0, Decimal("0"))
        )
        count_rejected, total_rejected = by_status.get(
            ExpenseClaimStatus.REJECTED.value, (0, Decimal("0"))
        )

        total_approved = sum(
            by_status.get(status, (0, Decimal("0")))[1]
            for status in (
                ExpenseClaimStatus.APPROVED.value,
                ExpenseClaimStatus.PARTIALLY_PAID.value,
                ExpenseClaimStatus.PAID.value,
            )
        )

        paid_total = await self.db.scalar(
            select(func.coalesce(func.sum(CompensationPayout.amount), 0)).where(
                CompensationPayout.employee_id == employee_id
            )
        )
        total_paid = Decimal(str(paid_total or 0))
        balance = total_approved - total_paid

        return EmployeeClaimTotalsResponse(
            employee_id=employee_id,
            total_submitted=round_money(total_submitted),
            count_submitted=count_submitted,
            total_pending_approval=round_money(total_pending),
            count_pending_approval=count_pending,
            total_approved=round_money(total_approved),
            total_paid=round_money(total_paid),
            balance=round_money(balance),
            total_rejected=round_money(total_rejected),
            count_rejected=count_rejected,
        )

"""Service layer for budgets and employee advances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.documents.number_generator import get_document_number
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.budgets.models import (
    Budget,
    BudgetAdvance,
    BudgetAdvanceReturn,
    BudgetAdvanceSourceType,
    BudgetAdvanceStatus,
    BudgetAdvanceTransfer,
    BudgetClaimAllocation,
    BudgetClaimAllocationStatus,
    BudgetStatus,
)
from src.modules.budgets.schemas import (
    BudgetAdvanceCreate,
    BudgetAdvanceIssueRequest,
    BudgetAdvanceReturnCreate,
    BudgetAdvanceTransferCreate,
    BudgetCreate,
    BudgetUpdate,
)
from src.modules.compensations.models import (
    BudgetFundingStatus,
    ExpenseClaim,
    ExpenseClaimStatus,
    FundingSource,
)
from src.modules.procurement.models import PaymentPurpose
from src.shared.utils.money import round_money


@dataclass(slots=True)
class BudgetTotals:
    direct_issue_total: Decimal
    transfer_in_total: Decimal
    returned_total: Decimal
    transfer_out_total: Decimal
    reserved_total: Decimal
    settled_total: Decimal
    committed_total: Decimal
    open_on_hands_total: Decimal
    available_unreserved_total: Decimal
    available_to_issue: Decimal
    overdue_advances_count: int


@dataclass(slots=True)
class AdvanceTotals:
    reserved_amount: Decimal
    settled_amount: Decimal
    returned_amount: Decimal
    transferred_out_amount: Decimal
    open_balance: Decimal
    available_unreserved_amount: Decimal


class BudgetService:
    """Manage operational budgets and employee advances."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _money(value: object | None) -> Decimal:
        return round_money(Decimal(str(value or 0)))

    async def _get_purpose(self, purpose_id: int) -> PaymentPurpose:
        purpose = await self.db.scalar(select(PaymentPurpose).where(PaymentPurpose.id == purpose_id))
        if not purpose:
            raise ValidationError("Invalid purpose_id")
        return purpose

    async def _get_budget_base(self, budget_id: int) -> Budget:
        budget = await self.db.scalar(
            select(Budget)
            .where(Budget.id == budget_id)
            .options(selectinload(Budget.purpose))
        )
        if not budget:
            raise NotFoundError("Budget", budget_id)
        await self._refresh_budget_period_state(budget)
        return budget

    async def _get_advance_base(self, advance_id: int) -> BudgetAdvance:
        advance = await self.db.scalar(
            select(BudgetAdvance)
            .where(BudgetAdvance.id == advance_id)
            .options(
                selectinload(BudgetAdvance.budget).selectinload(Budget.purpose),
                selectinload(BudgetAdvance.employee),
                selectinload(BudgetAdvance.returns),
                selectinload(BudgetAdvance.transfer_out_documents),
                selectinload(BudgetAdvance.allocations),
            )
        )
        if not advance:
            raise NotFoundError("Budget advance", advance_id)
        await self._refresh_budget_period_state(advance.budget)
        await self._refresh_advance_status(advance)
        return advance

    async def _refresh_budget_period_state(self, budget: Budget) -> None:
        if budget.status == BudgetStatus.ACTIVE.value and budget.period_to < date.today():
            budget.status = BudgetStatus.CLOSING.value
            await self.db.flush()

    async def _advance_totals(self, advance_id: int) -> AdvanceTotals:
        reserved_amount = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetClaimAllocation.allocated_amount), 0)).where(
                    BudgetClaimAllocation.advance_id == advance_id,
                    BudgetClaimAllocation.allocation_status == BudgetClaimAllocationStatus.RESERVED.value,
                )
            )
        )
        settled_amount = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetClaimAllocation.allocated_amount), 0)).where(
                    BudgetClaimAllocation.advance_id == advance_id,
                    BudgetClaimAllocation.allocation_status == BudgetClaimAllocationStatus.SETTLED.value,
                )
            )
        )
        returned_amount = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetAdvanceReturn.amount), 0)).where(
                    BudgetAdvanceReturn.advance_id == advance_id
                )
            )
        )
        transferred_out_amount = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetAdvanceTransfer.amount), 0)).where(
                    BudgetAdvanceTransfer.from_advance_id == advance_id
                )
            )
        )
        advance = await self.db.scalar(select(BudgetAdvance.amount_issued).where(BudgetAdvance.id == advance_id))
        amount_issued = self._money(advance)
        open_balance = round_money(amount_issued - settled_amount - returned_amount - transferred_out_amount)
        available_unreserved_amount = round_money(open_balance - reserved_amount)
        return AdvanceTotals(
            reserved_amount=reserved_amount,
            settled_amount=settled_amount,
            returned_amount=returned_amount,
            transferred_out_amount=transferred_out_amount,
            open_balance=max(Decimal("0.00"), open_balance),
            available_unreserved_amount=max(Decimal("0.00"), available_unreserved_amount),
        )

    async def _budget_totals(self, budget_id: int) -> BudgetTotals:
        direct_issue_total = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetAdvance.amount_issued), 0)).where(
                    BudgetAdvance.budget_id == budget_id,
                    BudgetAdvance.source_type == BudgetAdvanceSourceType.CASH_ISSUE.value,
                    BudgetAdvance.status != BudgetAdvanceStatus.DRAFT.value,
                    BudgetAdvance.status != BudgetAdvanceStatus.CANCELLED.value,
                )
            )
        )
        transfer_in_total = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetAdvance.amount_issued), 0)).where(
                    BudgetAdvance.budget_id == budget_id,
                    BudgetAdvance.source_type == BudgetAdvanceSourceType.TRANSFER_IN.value,
                    BudgetAdvance.status != BudgetAdvanceStatus.DRAFT.value,
                    BudgetAdvance.status != BudgetAdvanceStatus.CANCELLED.value,
                )
            )
        )
        returned_total = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetAdvanceReturn.amount), 0))
                .select_from(BudgetAdvanceReturn)
                .join(BudgetAdvance, BudgetAdvance.id == BudgetAdvanceReturn.advance_id)
                .where(BudgetAdvance.budget_id == budget_id)
            )
        )
        transfer_out_total = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetAdvanceTransfer.amount), 0))
                .select_from(BudgetAdvanceTransfer)
                .join(BudgetAdvance, BudgetAdvance.id == BudgetAdvanceTransfer.from_advance_id)
                .where(BudgetAdvance.budget_id == budget_id)
            )
        )
        reserved_total = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetClaimAllocation.allocated_amount), 0))
                .select_from(BudgetClaimAllocation)
                .join(BudgetAdvance, BudgetAdvance.id == BudgetClaimAllocation.advance_id)
                .where(
                    BudgetAdvance.budget_id == budget_id,
                    BudgetClaimAllocation.allocation_status == BudgetClaimAllocationStatus.RESERVED.value,
                )
            )
        )
        settled_total = self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetClaimAllocation.allocated_amount), 0))
                .select_from(BudgetClaimAllocation)
                .join(BudgetAdvance, BudgetAdvance.id == BudgetClaimAllocation.advance_id)
                .where(
                    BudgetAdvance.budget_id == budget_id,
                    BudgetClaimAllocation.allocation_status == BudgetClaimAllocationStatus.SETTLED.value,
                )
            )
        )
        overdue_advances_count = int(
            await self.db.scalar(
                select(func.count(BudgetAdvance.id)).where(
                    BudgetAdvance.budget_id == budget_id,
                    BudgetAdvance.status == BudgetAdvanceStatus.OVERDUE.value,
                )
            )
            or 0
        )
        budget_limit = self._money(await self.db.scalar(select(Budget.limit_amount).where(Budget.id == budget_id)))
        committed_total = round_money(direct_issue_total + transfer_in_total - returned_total - transfer_out_total)
        open_on_hands_total = round_money(committed_total - settled_total)
        available_unreserved_total = round_money(open_on_hands_total - reserved_total)
        available_to_issue = round_money(budget_limit - committed_total)
        return BudgetTotals(
            direct_issue_total=direct_issue_total,
            transfer_in_total=transfer_in_total,
            returned_total=returned_total,
            transfer_out_total=transfer_out_total,
            reserved_total=reserved_total,
            settled_total=settled_total,
            committed_total=max(Decimal("0.00"), committed_total),
            open_on_hands_total=max(Decimal("0.00"), open_on_hands_total),
            available_unreserved_total=max(Decimal("0.00"), available_unreserved_total),
            available_to_issue=available_to_issue,
            overdue_advances_count=overdue_advances_count,
        )

    async def _refresh_advance_status(self, advance: BudgetAdvance) -> None:
        if advance.status in (
            BudgetAdvanceStatus.DRAFT.value,
            BudgetAdvanceStatus.CANCELLED.value,
            BudgetAdvanceStatus.CLOSED.value,
        ):
            return

        totals = await self._advance_totals(advance.id)
        if totals.open_balance <= 0:
            advance.status = BudgetAdvanceStatus.SETTLED.value
        elif advance.settlement_due_date < date.today():
            advance.status = BudgetAdvanceStatus.OVERDUE.value
        else:
            advance.status = BudgetAdvanceStatus.ISSUED.value
        await self.db.flush()

    async def _employee_budget_available_total(self, budget_id: int, employee_id: int) -> Decimal:
        result = await self.db.execute(
            select(BudgetAdvance.id)
            .where(
                BudgetAdvance.budget_id == budget_id,
                BudgetAdvance.employee_id == employee_id,
                BudgetAdvance.status.in_(
                    [
                        BudgetAdvanceStatus.ISSUED.value,
                        BudgetAdvanceStatus.OVERDUE.value,
                        BudgetAdvanceStatus.SETTLED.value,
                    ]
                ),
            )
            .order_by(BudgetAdvance.issue_date.asc(), BudgetAdvance.id.asc())
        )
        total = Decimal("0.00")
        for advance_id in result.scalars().all():
            totals = await self._advance_totals(advance_id)
            total += totals.available_unreserved_amount
        return round_money(total)

    async def get_employee_budget_available_total(self, budget_id: int, employee_id: int) -> Decimal:
        """Public wrapper for employee-specific available balance inside one budget."""
        return await self._employee_budget_available_total(budget_id, employee_id)

    async def _claim_allocations_total(self, claim_id: int, *, statuses: list[str]) -> Decimal:
        return self._money(
            await self.db.scalar(
                select(func.coalesce(func.sum(BudgetClaimAllocation.allocated_amount), 0)).where(
                    BudgetClaimAllocation.claim_id == claim_id,
                    BudgetClaimAllocation.allocation_status.in_(statuses),
                )
            )
        )

    async def create_budget(self, data: BudgetCreate, created_by_id: int) -> Budget:
        await self._get_purpose(data.purpose_id)
        budget_number = await get_document_number(self.db, "BGT")
        budget = Budget(
            budget_number=budget_number,
            name=data.name.strip(),
            purpose_id=data.purpose_id,
            period_from=data.period_from,
            period_to=data.period_to,
            limit_amount=round_money(data.limit_amount),
            notes=data.notes,
            status=BudgetStatus.DRAFT.value,
            created_by_id=created_by_id,
        )
        self.db.add(budget)
        await self.db.commit()
        return await self.get_budget_by_id(budget.id)

    async def update_budget(self, budget_id: int, data: BudgetUpdate) -> Budget:
        budget = await self._get_budget_base(budget_id)
        update = data.model_dump(exclude_unset=True)

        protected_fields = {"purpose_id", "period_from", "period_to", "limit_amount"}
        if budget.status != BudgetStatus.DRAFT.value and protected_fields.intersection(update):
            raise ValidationError("Only draft budgets can change purpose, period, or limit_amount")

        for field, value in update.items():
            setattr(budget, field, value)

        if budget.period_from > budget.period_to:
            raise ValidationError("period_from must be <= period_to")

        totals = await self._budget_totals(budget.id)
        if round_money(budget.limit_amount) < totals.committed_total:
            raise ValidationError("limit_amount cannot be lower than already committed budget amount")

        await self.db.commit()
        return await self.get_budget_by_id(budget.id)

    async def activate_budget(self, budget_id: int, approved_by_id: int) -> Budget:
        budget = await self._get_budget_base(budget_id)
        if budget.status != BudgetStatus.DRAFT.value:
            raise ValidationError("Only draft budgets can be activated")
        budget.status = (
            BudgetStatus.CLOSING.value if budget.period_to < date.today() else BudgetStatus.ACTIVE.value
        )
        budget.approved_by_id = approved_by_id
        await self.db.commit()
        return await self.get_budget_by_id(budget.id)

    async def cancel_budget(self, budget_id: int) -> Budget:
        budget = await self._get_budget_base(budget_id)
        if budget.status == BudgetStatus.CANCELLED.value:
            return budget
        advances_count = int(
            await self.db.scalar(
                select(func.count(BudgetAdvance.id)).where(
                    BudgetAdvance.budget_id == budget.id,
                    BudgetAdvance.status != BudgetAdvanceStatus.CANCELLED.value,
                )
            )
            or 0
        )
        claims_count = int(
            await self.db.scalar(
                select(func.count(ExpenseClaim.id)).where(ExpenseClaim.budget_id == budget.id)
            )
            or 0
        )
        if advances_count or claims_count:
            raise ValidationError("Budget with advances or claims cannot be cancelled")
        budget.status = BudgetStatus.CANCELLED.value
        await self.db.commit()
        return await self.get_budget_by_id(budget.id)

    async def get_budget_by_id(self, budget_id: int) -> Budget:
        budget = await self._get_budget_base(budget_id)
        await self.db.commit()
        return budget

    async def list_budgets(
        self,
        *,
        status: str | None = None,
        purpose_id: int | None = None,
        employee_id: int | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Budget], int]:
        query = select(Budget).options(selectinload(Budget.purpose))
        if status:
            query = query.where(Budget.status == status)
        if purpose_id:
            query = query.where(Budget.purpose_id == purpose_id)
        total = int((await self.db.scalar(select(func.count()).select_from(query.subquery()))) or 0)
        rows = list(
            (
                await self.db.execute(
                    query.order_by(Budget.period_from.desc(), Budget.id.desc()).offset((page - 1) * limit).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        for budget in rows:
            await self._refresh_budget_period_state(budget)
        if employee_id is not None:
            filtered: list[Budget] = []
            for budget in rows:
                available = await self._employee_budget_available_total(budget.id, employee_id)
                if available > 0:
                    filtered.append(budget)
            rows = filtered
        await self.db.commit()
        return rows, len(rows) if employee_id is not None else total

    async def get_budget_closure_status(self, budget_id: int) -> dict:
        budget = await self._get_budget_base(budget_id)
        open_advances_count = 0
        overdue_advances_count = 0
        transferable_amount_total = Decimal("0.00")
        advance_ids = list(
            (
                await self.db.execute(
                    select(BudgetAdvance.id).where(
                        BudgetAdvance.budget_id == budget.id,
                        BudgetAdvance.status != BudgetAdvanceStatus.CANCELLED.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        for advance_id in advance_ids:
            advance = await self._get_advance_base(advance_id)
            totals = await self._advance_totals(advance.id)
            if totals.open_balance > 0:
                open_advances_count += 1
            if advance.status == BudgetAdvanceStatus.OVERDUE.value:
                overdue_advances_count += 1
            transferable_amount_total += totals.available_unreserved_amount

        unresolved_claims_count = int(
            await self.db.scalar(
                select(func.count(ExpenseClaim.id)).where(
                    ExpenseClaim.budget_id == budget.id,
                    ExpenseClaim.status.notin_(
                        [ExpenseClaimStatus.REJECTED.value, ExpenseClaimStatus.PAID.value]
                    ),
                )
            )
            or 0
        )
        blocking_reasons: list[str] = []
        if open_advances_count:
            blocking_reasons.append("There are advances with open balance")
        if unresolved_claims_count:
            blocking_reasons.append("There are unresolved budget claims")
        return {
            "budget_id": budget.id,
            "open_advances_count": open_advances_count,
            "overdue_advances_count": overdue_advances_count,
            "unresolved_claims_count": unresolved_claims_count,
            "transferable_amount_total": round_money(transferable_amount_total),
            "can_close": not blocking_reasons,
            "blocking_reasons": blocking_reasons,
        }

    async def close_budget(self, budget_id: int) -> Budget:
        budget = await self._get_budget_base(budget_id)
        closure = await self.get_budget_closure_status(budget.id)
        if not closure["can_close"]:
            raise ValidationError("; ".join(closure["blocking_reasons"]))
        budget.status = BudgetStatus.CLOSED.value
        await self.db.commit()
        return await self.get_budget_by_id(budget.id)

    async def create_advance(self, data: BudgetAdvanceCreate, created_by_id: int) -> BudgetAdvance:
        budget = await self._get_budget_base(data.budget_id)
        if budget.status != BudgetStatus.ACTIVE.value:
            raise ValidationError("Only active budgets can create advances")
        if data.issue_date < budget.period_from or data.issue_date > budget.period_to:
            raise ValidationError("Advance issue_date must be inside budget period")
        due_date = data.settlement_due_date or budget.period_to
        if due_date < data.issue_date:
            raise ValidationError("settlement_due_date must be >= issue_date")

        amount_issued = round_money(data.amount_issued)
        if data.issue_now:
            totals = await self._budget_totals(budget.id)
            if amount_issued > totals.available_to_issue:
                raise ValidationError("Advance exceeds available budget headroom")

        from src.core.auth.service import AuthService

        if not await AuthService(self.db).get_user_by_id(data.employee_id):
            raise ValidationError("Employee not found")

        advance_number = await get_document_number(self.db, "BADV")
        advance = BudgetAdvance(
            advance_number=advance_number,
            budget_id=budget.id,
            employee_id=data.employee_id,
            issue_date=data.issue_date,
            amount_issued=amount_issued,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            proof_text=data.proof_text,
            proof_attachment_id=data.proof_attachment_id,
            notes=data.notes,
            source_type=BudgetAdvanceSourceType.CASH_ISSUE.value,
            settlement_due_date=due_date,
            status=BudgetAdvanceStatus.ISSUED.value if data.issue_now else BudgetAdvanceStatus.DRAFT.value,
            created_by_id=created_by_id,
        )
        self.db.add(advance)
        await self.db.flush()
        if data.issue_now:
            await self._refresh_advance_status(advance)
        await self.db.commit()
        return await self.get_advance_by_id(advance.id)

    async def issue_advance(self, advance_id: int, data: BudgetAdvanceIssueRequest) -> BudgetAdvance:
        advance = await self._get_advance_base(advance_id)
        if advance.status != BudgetAdvanceStatus.DRAFT.value:
            raise ValidationError("Only draft advances can be issued")
        budget = advance.budget
        if budget.status != BudgetStatus.ACTIVE.value:
            raise ValidationError("Only active budgets can issue advances")

        if data.issue_date is not None:
            advance.issue_date = data.issue_date
        if data.payment_method is not None:
            advance.payment_method = data.payment_method
        if data.reference_number is not None:
            advance.reference_number = data.reference_number
        if data.proof_text is not None:
            advance.proof_text = data.proof_text
        if data.proof_attachment_id is not None:
            advance.proof_attachment_id = data.proof_attachment_id
        if data.notes is not None:
            advance.notes = data.notes
        if data.settlement_due_date is not None:
            advance.settlement_due_date = data.settlement_due_date

        if advance.issue_date < budget.period_from or advance.issue_date > budget.period_to:
            raise ValidationError("Advance issue_date must be inside budget period")
        if advance.settlement_due_date < advance.issue_date:
            raise ValidationError("settlement_due_date must be >= issue_date")
        if not (advance.reference_number or advance.proof_text or advance.proof_attachment_id):
            raise ValidationError("reference_number or proof is required")

        totals = await self._budget_totals(budget.id)
        if round_money(advance.amount_issued) > totals.available_to_issue:
            raise ValidationError("Advance exceeds available budget headroom")

        advance.status = BudgetAdvanceStatus.ISSUED.value
        await self._refresh_advance_status(advance)
        await self.db.commit()
        return await self.get_advance_by_id(advance.id)

    async def cancel_advance(self, advance_id: int) -> BudgetAdvance:
        advance = await self._get_advance_base(advance_id)
        if advance.status != BudgetAdvanceStatus.DRAFT.value:
            raise ValidationError("Only draft advances can be cancelled")
        advance.status = BudgetAdvanceStatus.CANCELLED.value
        await self.db.commit()
        return await self.get_advance_by_id(advance.id)

    async def close_advance(self, advance_id: int) -> BudgetAdvance:
        advance = await self._get_advance_base(advance_id)
        totals = await self._advance_totals(advance.id)
        if totals.open_balance > 0 or totals.reserved_amount > 0:
            raise ValidationError("Advance cannot be closed while balance or reservations remain")
        advance.status = BudgetAdvanceStatus.CLOSED.value
        await self.db.commit()
        return await self.get_advance_by_id(advance.id)

    async def get_advance_by_id(self, advance_id: int) -> BudgetAdvance:
        advance = await self._get_advance_base(advance_id)
        await self.db.commit()
        return advance

    async def list_advances(
        self,
        *,
        budget_id: int | None = None,
        employee_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[BudgetAdvance], int]:
        query = select(BudgetAdvance).options(
            selectinload(BudgetAdvance.budget),
            selectinload(BudgetAdvance.employee),
        )
        if budget_id:
            query = query.where(BudgetAdvance.budget_id == budget_id)
        if employee_id:
            query = query.where(BudgetAdvance.employee_id == employee_id)
        if status:
            query = query.where(BudgetAdvance.status == status)

        total = int((await self.db.scalar(select(func.count()).select_from(query.subquery()))) or 0)
        items = list(
            (
                await self.db.execute(
                    query.order_by(BudgetAdvance.issue_date.desc(), BudgetAdvance.id.desc())
                    .offset((page - 1) * limit)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        for advance in items:
            await self._refresh_advance_status(advance)
        await self.db.commit()
        return items, total

    async def create_return(
        self, advance_id: int, data: BudgetAdvanceReturnCreate, created_by_id: int
    ) -> BudgetAdvanceReturn:
        advance = await self._get_advance_base(advance_id)
        if advance.status not in (BudgetAdvanceStatus.ISSUED.value, BudgetAdvanceStatus.OVERDUE.value):
            raise ValidationError("Only issued or overdue advances can accept returns")
        if data.return_date < advance.issue_date:
            raise ValidationError("return_date cannot be before issue_date")

        totals = await self._advance_totals(advance.id)
        if round_money(data.amount) > totals.available_unreserved_amount:
            raise ValidationError("Return exceeds available unreserved balance on advance")

        return_number = await get_document_number(self.db, "BRT")
        row = BudgetAdvanceReturn(
            return_number=return_number,
            advance_id=advance.id,
            return_date=data.return_date,
            amount=round_money(data.amount),
            return_method=data.return_method,
            reference_number=data.reference_number,
            proof_text=data.proof_text,
            proof_attachment_id=data.proof_attachment_id,
            notes=data.notes,
            created_by_id=created_by_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self._refresh_advance_status(advance)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_returns_for_advance(self, advance_id: int) -> list[BudgetAdvanceReturn]:
        await self._get_advance_base(advance_id)
        result = await self.db.execute(
            select(BudgetAdvanceReturn)
            .where(BudgetAdvanceReturn.advance_id == advance_id)
            .order_by(BudgetAdvanceReturn.return_date.desc(), BudgetAdvanceReturn.id.desc())
        )
        return list(result.scalars().all())

    async def transfer_advance(
        self, advance_id: int, data: BudgetAdvanceTransferCreate, created_by_id: int
    ) -> BudgetAdvanceTransfer:
        source = await self._get_advance_base(advance_id)
        if source.status not in (BudgetAdvanceStatus.ISSUED.value, BudgetAdvanceStatus.OVERDUE.value):
            raise ValidationError("Only issued or overdue advances can be transferred")

        source_totals = await self._advance_totals(source.id)
        if round_money(data.amount) > source_totals.available_unreserved_amount:
            raise ValidationError("Transfer exceeds available unreserved balance on advance")

        target_budget = await self._get_budget_base(data.to_budget_id)
        if target_budget.status != BudgetStatus.ACTIVE.value:
            raise ValidationError("Transfers can only target active budgets")
        if data.transfer_date < target_budget.period_from or data.transfer_date > target_budget.period_to:
            raise ValidationError("transfer_date must be inside target budget period")
        target_budget_totals = await self._budget_totals(target_budget.id)
        if round_money(data.amount) > target_budget_totals.available_to_issue:
            raise ValidationError("Transfer exceeds available target budget headroom")

        target_employee_id = data.to_employee_id or source.employee_id
        target_due_date = data.settlement_due_date or target_budget.period_to
        if target_due_date < data.transfer_date:
            raise ValidationError("settlement_due_date must be >= transfer_date")

        from src.core.auth.service import AuthService

        if not await AuthService(self.db).get_user_by_id(target_employee_id):
            raise ValidationError("Employee not found")

        target_advance_number = await get_document_number(self.db, "BADV")
        created_to_advance = BudgetAdvance(
            advance_number=target_advance_number,
            budget_id=target_budget.id,
            employee_id=target_employee_id,
            issue_date=data.transfer_date,
            amount_issued=round_money(data.amount),
            payment_method=source.payment_method,
            reference_number=source.reference_number,
            proof_text=source.proof_text,
            proof_attachment_id=source.proof_attachment_id,
            notes=f"Transfer in from {source.advance_number}",
            source_type=BudgetAdvanceSourceType.TRANSFER_IN.value,
            settlement_due_date=target_due_date,
            status=BudgetAdvanceStatus.ISSUED.value,
            created_by_id=created_by_id,
        )
        self.db.add(created_to_advance)
        await self.db.flush()

        transfer_number = await get_document_number(self.db, "BTR")
        transfer = BudgetAdvanceTransfer(
            transfer_number=transfer_number,
            from_advance_id=source.id,
            to_budget_id=target_budget.id,
            to_employee_id=target_employee_id,
            transfer_date=data.transfer_date,
            amount=round_money(data.amount),
            transfer_type=data.transfer_type,
            reason=data.reason.strip(),
            created_to_advance_id=created_to_advance.id,
            created_by_id=created_by_id,
        )
        self.db.add(transfer)
        await self.db.flush()

        await self._refresh_advance_status(source)
        await self._refresh_advance_status(created_to_advance)
        await self.db.commit()
        return await self.get_transfer_by_id(transfer.id)

    async def get_transfer_by_id(self, transfer_id: int) -> BudgetAdvanceTransfer:
        transfer = await self.db.scalar(
            select(BudgetAdvanceTransfer)
            .where(BudgetAdvanceTransfer.id == transfer_id)
            .options(
                selectinload(BudgetAdvanceTransfer.from_advance),
                selectinload(BudgetAdvanceTransfer.to_budget),
                selectinload(BudgetAdvanceTransfer.to_employee),
                selectinload(BudgetAdvanceTransfer.created_to_advance),
            )
        )
        if not transfer:
            raise NotFoundError("Budget advance transfer", transfer_id)
        return transfer

    async def list_transfers(
        self,
        *,
        budget_id: int | None = None,
        employee_id: int | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[BudgetAdvanceTransfer], int]:
        query = select(BudgetAdvanceTransfer).options(
            selectinload(BudgetAdvanceTransfer.from_advance),
            selectinload(BudgetAdvanceTransfer.to_budget),
            selectinload(BudgetAdvanceTransfer.to_employee),
            selectinload(BudgetAdvanceTransfer.created_to_advance),
        )
        if budget_id:
            query = query.where(BudgetAdvanceTransfer.to_budget_id == budget_id)
        if employee_id:
            query = query.where(BudgetAdvanceTransfer.to_employee_id == employee_id)
        total = int((await self.db.scalar(select(func.count()).select_from(query.subquery()))) or 0)
        items = list(
            (
                await self.db.execute(
                    query.order_by(BudgetAdvanceTransfer.transfer_date.desc(), BudgetAdvanceTransfer.id.desc())
                    .offset((page - 1) * limit)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return items, total

    async def list_available_budgets_for_employee(self, employee_id: int) -> list[Budget]:
        budgets = list(
            (
                await self.db.execute(
                    select(Budget)
                    .join(BudgetAdvance, BudgetAdvance.budget_id == Budget.id)
                    .where(
                        BudgetAdvance.employee_id == employee_id,
                        Budget.status.in_([BudgetStatus.ACTIVE.value, BudgetStatus.CLOSING.value]),
                    )
                    .options(selectinload(Budget.purpose))
                    .distinct()
                    .order_by(Budget.period_from.desc(), Budget.id.desc())
                )
            )
            .scalars()
            .all()
        )
        filtered: list[Budget] = []
        for budget in budgets:
            await self._refresh_budget_period_state(budget)
            available = await self._employee_budget_available_total(budget.id, employee_id)
            if available > 0:
                filtered.append(budget)
        await self.db.commit()
        return filtered

    async def reserve_claim_allocations(self, claim_id: int) -> None:
        claim = await self.db.scalar(
            select(ExpenseClaim)
            .where(ExpenseClaim.id == claim_id)
            .options(
                selectinload(ExpenseClaim.budget),
                selectinload(ExpenseClaim.budget_allocations),
            )
        )
        if not claim:
            raise NotFoundError("Expense claim", claim_id)
        if claim.funding_source != FundingSource.BUDGET.value or not claim.budget_id:
            raise ValidationError("Claim is not budget-funded")

        budget = await self._get_budget_base(claim.budget_id)
        if claim.expense_date < budget.period_from or claim.expense_date > budget.period_to:
            raise ValidationError("Claim expense_date must be inside budget period")
        if claim.purpose_id != budget.purpose_id:
            raise ValidationError("Claim purpose must match budget purpose")
        if budget.status not in (BudgetStatus.ACTIVE.value, BudgetStatus.CLOSING.value):
            raise ValidationError("Budget is not open for claims")

        if claim.status not in (
            ExpenseClaimStatus.DRAFT.value,
            ExpenseClaimStatus.NEEDS_EDIT.value,
            ExpenseClaimStatus.PENDING_APPROVAL.value,
        ):
            raise ValidationError("Claim is not in a reservable state")

        if any(a.allocation_status == BudgetClaimAllocationStatus.RESERVED.value for a in claim.budget_allocations):
            await self.release_claim_allocations(claim.id, "Re-reserved after claim change")
            await self.db.refresh(claim)

        required_amount = round_money(claim.amount)
        available_total = await self._employee_budget_available_total(claim.budget_id, claim.employee_id)
        if available_total < required_amount:
            raise ValidationError("Claim exceeds available budget balance for employee")

        advance_ids = list(
            (
                await self.db.execute(
                    select(BudgetAdvance.id)
                    .where(
                        BudgetAdvance.budget_id == claim.budget_id,
                        BudgetAdvance.employee_id == claim.employee_id,
                        BudgetAdvance.status.in_(
                            [
                                BudgetAdvanceStatus.ISSUED.value,
                                BudgetAdvanceStatus.OVERDUE.value,
                                BudgetAdvanceStatus.SETTLED.value,
                            ]
                        ),
                    )
                    .order_by(BudgetAdvance.issue_date.asc(), BudgetAdvance.id.asc())
                )
            )
            .scalars()
            .all()
        )

        remaining = required_amount
        for advance_id in advance_ids:
            if remaining <= 0:
                break
            totals = await self._advance_totals(advance_id)
            if totals.available_unreserved_amount <= 0:
                continue
            allocated = min(remaining, totals.available_unreserved_amount)
            self.db.add(
                BudgetClaimAllocation(
                    advance_id=advance_id,
                    claim_id=claim.id,
                    allocated_amount=allocated,
                    allocation_status=BudgetClaimAllocationStatus.RESERVED.value,
                )
            )
            remaining = round_money(remaining - allocated)

        if remaining > 0:
            raise ValidationError("Failed to reserve full claim amount from available advances")

        claim.budget_funding_status = BudgetFundingStatus.RESERVED.value
        await self.db.flush()

        touched_advances = {a.advance_id for a in claim.budget_allocations}
        touched_advances.update(advance_ids)
        for advance_id in touched_advances:
            advance = await self.db.scalar(select(BudgetAdvance).where(BudgetAdvance.id == advance_id))
            if advance:
                await self._refresh_advance_status(advance)

    async def release_claim_allocations(self, claim_id: int, reason: str) -> None:
        claim = await self.db.scalar(
            select(ExpenseClaim)
            .where(ExpenseClaim.id == claim_id)
            .options(selectinload(ExpenseClaim.budget_allocations))
        )
        if not claim:
            raise NotFoundError("Expense claim", claim_id)

        touched: set[int] = set()
        released_any = False
        for allocation in claim.budget_allocations:
            if allocation.allocation_status != BudgetClaimAllocationStatus.RESERVED.value:
                continue
            allocation.allocation_status = BudgetClaimAllocationStatus.RELEASED.value
            allocation.released_reason = reason
            touched.add(allocation.advance_id)
            released_any = True

        if released_any:
            claim.budget_funding_status = BudgetFundingStatus.RELEASED.value
            await self.db.flush()
            for advance_id in touched:
                advance = await self.db.scalar(select(BudgetAdvance).where(BudgetAdvance.id == advance_id))
                if advance:
                    await self._refresh_advance_status(advance)

    async def settle_claim_allocations(self, claim_id: int) -> None:
        claim = await self.db.scalar(
            select(ExpenseClaim)
            .where(ExpenseClaim.id == claim_id)
            .options(selectinload(ExpenseClaim.budget_allocations))
        )
        if not claim:
            raise NotFoundError("Expense claim", claim_id)
        if claim.funding_source != FundingSource.BUDGET.value:
            raise ValidationError("Claim is not budget-funded")

        reserved_total = await self._claim_allocations_total(
            claim.id, statuses=[BudgetClaimAllocationStatus.RESERVED.value]
        )
        settled_total = await self._claim_allocations_total(
            claim.id, statuses=[BudgetClaimAllocationStatus.SETTLED.value]
        )
        if reserved_total + settled_total < round_money(claim.amount):
            await self.reserve_claim_allocations(claim.id)
            claim = await self.db.scalar(
                select(ExpenseClaim)
                .where(ExpenseClaim.id == claim_id)
                .options(selectinload(ExpenseClaim.budget_allocations))
            )
            if not claim:
                raise NotFoundError("Expense claim", claim_id)

        touched: set[int] = set()
        for allocation in claim.budget_allocations:
            if allocation.allocation_status != BudgetClaimAllocationStatus.RESERVED.value:
                continue
            allocation.allocation_status = BudgetClaimAllocationStatus.SETTLED.value
            allocation.released_reason = None
            touched.add(allocation.advance_id)

        claim.budget_funding_status = BudgetFundingStatus.SETTLED.value
        claim.paid_amount = round_money(claim.amount)
        claim.remaining_amount = Decimal("0.00")
        claim.status = ExpenseClaimStatus.PAID.value
        await self.db.flush()

        for advance_id in touched:
            advance = await self.db.scalar(select(BudgetAdvance).where(BudgetAdvance.id == advance_id))
            if advance:
                await self._refresh_advance_status(advance)

    async def get_budget_snapshot(self, budget: Budget) -> dict:
        totals = await self._budget_totals(budget.id)
        return {
            "id": budget.id,
            "budget_number": budget.budget_number,
            "name": budget.name,
            "purpose_id": budget.purpose_id,
            "purpose_name": getattr(getattr(budget, "purpose", None), "name", None),
            "period_from": budget.period_from,
            "period_to": budget.period_to,
            "limit_amount": round_money(budget.limit_amount),
            "notes": budget.notes,
            "status": budget.status,
            "created_by_id": budget.created_by_id,
            "approved_by_id": budget.approved_by_id,
            "created_at": budget.created_at,
            "updated_at": budget.updated_at,
            "direct_issue_total": totals.direct_issue_total,
            "transfer_in_total": totals.transfer_in_total,
            "returned_total": totals.returned_total,
            "transfer_out_total": totals.transfer_out_total,
            "reserved_total": totals.reserved_total,
            "settled_total": totals.settled_total,
            "committed_total": totals.committed_total,
            "open_on_hands_total": totals.open_on_hands_total,
            "available_unreserved_total": totals.available_unreserved_total,
            "available_to_issue": totals.available_to_issue,
            "overdue_advances_count": totals.overdue_advances_count,
        }

    async def get_advance_snapshot(self, advance: BudgetAdvance) -> dict:
        totals = await self._advance_totals(advance.id)
        return {
            "id": advance.id,
            "advance_number": advance.advance_number,
            "budget_id": advance.budget_id,
            "budget_number": advance.budget.budget_number,
            "budget_name": advance.budget.name,
            "employee_id": advance.employee_id,
            "employee_name": advance.employee.full_name,
            "issue_date": advance.issue_date,
            "amount_issued": round_money(advance.amount_issued),
            "payment_method": advance.payment_method,
            "reference_number": advance.reference_number,
            "proof_text": advance.proof_text,
            "proof_attachment_id": advance.proof_attachment_id,
            "notes": advance.notes,
            "source_type": advance.source_type,
            "settlement_due_date": advance.settlement_due_date,
            "status": advance.status,
            "created_by_id": advance.created_by_id,
            "created_at": advance.created_at,
            "updated_at": advance.updated_at,
            "reserved_amount": totals.reserved_amount,
            "settled_amount": totals.settled_amount,
            "returned_amount": totals.returned_amount,
            "transferred_out_amount": totals.transferred_out_amount,
            "open_balance": totals.open_balance,
            "available_unreserved_amount": totals.available_unreserved_amount,
        }

"""Budget changes and fee cancellation must share the claim transaction."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import ValidationError
from src.modules.budgets.models import Budget, BudgetAdvance
from src.modules.compensations.schemas import ExpenseClaimCreate, ExpenseClaimUpdate
from src.modules.compensations.service import ExpenseClaimService
from src.modules.procurement.models import PaymentPurpose, ProcurementPayment


@pytest.mark.parametrize("target_balance", [Decimal("100.00"), Decimal("2000.00")])
async def test_budget_change_and_fee_removal_are_atomic(
    db_session: AsyncSession, target_balance: Decimal
):
    employee = await AuthService(db_session).create_user(
        email="atomic-claim@test.com",
        password="Pass123!",
        full_name="Budget Employee",
        role=UserRole.USER,
    )
    purpose = PaymentPurpose(name="Supplies", is_active=True)
    db_session.add(purpose)
    await db_session.flush()
    employee_id = employee.id
    budgets = []
    advances = []
    for index, balance in enumerate([Decimal("2000.00"), target_balance]):
        budget = Budget(
            budget_number=f"BDG-ATOMIC-{index}",
            name=f"Supplies {index}",
            purpose_id=purpose.id,
            period_from=date(2099, 4, 1),
            period_to=date(2099, 4, 30),
            limit_amount=Decimal("5000.00"),
            status="active",
            created_by_id=employee_id,
        )
        db_session.add(budget)
        await db_session.flush()
        advance = BudgetAdvance(
            advance_number=f"BADV-ATOMIC-{index}",
            budget_id=budget.id,
            employee_id=employee_id,
            issue_date=date(2099, 4, 1),
            amount_issued=balance,
            payment_method="bank",
            status="issued",
            settlement_due_date=date(2099, 4, 30),
            created_by_id=employee_id,
        )
        db_session.add(advance)
        budgets.append(budget)
        advances.append(advance)
    await db_session.commit()
    old_budget_id, new_budget_id = [budget.id for budget in budgets]
    old_advance_id, new_advance_id = [advance.id for advance in advances]
    service = ExpenseClaimService(db_session)
    claim = await service.create_out_of_pocket_claim(
        ExpenseClaimCreate(
            budget_id=old_budget_id,
            funding_source="budget",
            purpose_id=purpose.id,
            amount=Decimal("1200.00"),
            fee_amount=Decimal("25.00"),
            fee_proof_text="Fee receipt",
            description="Supplies",
            expense_date=date(2099, 4, 24),
            proof_text="Receipt",
            submit=True,
        ),
        employee_id=employee_id,
        created_by_id=employee_id,
    )
    claim_id, fee_payment_id = claim.id, claim.fee_payment_id
    original_allocation_id = claim.budget_allocations[0].id
    update = ExpenseClaimUpdate(budget_id=new_budget_id, fee_amount=Decimal("0.00"))
    insufficient = target_balance < Decimal("1200.00")
    if insufficient:
        with pytest.raises(ValidationError, match="exceeds available budget balance"):
            await service.update_out_of_pocket_claim(claim_id, update, employee_id=employee_id)
        # The request dependency rolls back when the service raises.
        await db_session.rollback()
    else:
        await service.update_out_of_pocket_claim(claim_id, update, employee_id=employee_id)

    # Read persisted state in a fresh session, not from the identity map.
    sessions = async_sessionmaker(db_session.bind, expire_on_commit=False)
    async with sessions() as verification:
        persisted = await ExpenseClaimService(verification).get_claim_by_id(claim_id)
        fee = await verification.get(ProcurementPayment, fee_payment_id)
        expected_budget = old_budget_id if insufficient else new_budget_id
        assert persisted.budget_id == expected_budget
        assert persisted.payment.budget_id == expected_budget
        assert fee.budget_id == expected_budget
        assert fee.status == ("posted" if insufficient else "cancelled")
        assert persisted.fee_payment_id == (fee_payment_id if insufficient else None)
        assert persisted.fee_amount == (Decimal("25.00") if insufficient else Decimal("0.00"))
        expected_amount = Decimal("1225.00") if insufficient else Decimal("1200.00")
        assert persisted.amount == expected_amount
        assert persisted.remaining_amount == expected_amount
        assert persisted.budget_funding_status == "reserved"
        reserved = [a for a in persisted.budget_allocations if a.allocation_status == "reserved"]
        assert len(reserved) == 1
        assert reserved[0].advance_id == (old_advance_id if insufficient else new_advance_id)
        assert reserved[0].allocated_amount == expected_amount
        if insufficient:
            assert len(persisted.budget_allocations) == 1
            assert reserved[0].id == original_allocation_id
            assert reserved[0].released_reason is None
            assert fee.cancelled_at is None

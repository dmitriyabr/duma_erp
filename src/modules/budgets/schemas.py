"""Schemas for budgets and employee advances."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.shared.schemas.base import BaseSchema


class BudgetCreate(BaseSchema):
    """Create operational budget."""

    name: str = Field(..., min_length=1, max_length=300)
    purpose_id: int
    period_from: date
    period_to: date
    limit_amount: Decimal = Field(..., gt=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_from > self.period_to:
            raise ValueError("period_from must be <= period_to")
        return self


class BudgetUpdate(BaseSchema):
    """Update operational budget."""

    name: str | None = Field(None, min_length=1, max_length=300)
    purpose_id: int | None = None
    period_from: date | None = None
    period_to: date | None = None
    limit_amount: Decimal | None = Field(None, gt=0)
    notes: str | None = None


class BudgetResponse(BaseSchema):
    """Budget with computed totals."""

    id: int
    budget_number: str
    name: str
    purpose_id: int
    purpose_name: str | None = None
    period_from: date
    period_to: date
    limit_amount: Decimal
    notes: str | None
    status: str
    created_by_id: int
    approved_by_id: int | None
    created_at: datetime
    updated_at: datetime
    direct_company_paid_total: Decimal
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


class BudgetClosureStatusResponse(BaseSchema):
    """Whether the budget can be closed safely."""

    budget_id: int
    open_advances_count: int
    overdue_advances_count: int
    unresolved_claims_count: int
    transferable_amount_total: Decimal
    can_close: bool
    blocking_reasons: list[str]


class BudgetAdvanceCreate(BaseSchema):
    """Create a draft or immediately issue a budget advance."""

    budget_id: int
    employee_id: int
    issue_date: date
    amount_issued: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., min_length=1, max_length=20)
    reference_number: str | None = Field(None, max_length=200)
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    notes: str | None = None
    settlement_due_date: date | None = None
    issue_now: bool = True

    @model_validator(mode="after")
    def validate_supporting_data(self):
        if self.issue_now and not (self.reference_number or self.proof_text or self.proof_attachment_id):
            raise ValueError("reference_number or proof is required when issuing advance")
        return self


class BudgetAdvanceIssueRequest(BaseSchema):
    """Issue an existing draft advance."""

    issue_date: date | None = None
    payment_method: str | None = Field(None, min_length=1, max_length=20)
    reference_number: str | None = Field(None, max_length=200)
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    notes: str | None = None
    settlement_due_date: date | None = None

    @model_validator(mode="after")
    def validate_supporting_data(self):
        if not (self.reference_number or self.proof_text or self.proof_attachment_id):
            raise ValueError("reference_number or proof is required")
        return self


class BudgetAdvanceReturnCreate(BaseSchema):
    """Record a return of unused advance money."""

    return_date: date
    amount: Decimal = Field(..., gt=0)
    return_method: str = Field(..., min_length=1, max_length=20)
    reference_number: str | None = Field(None, max_length=200)
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_supporting_data(self):
        if not (self.reference_number or self.proof_text or self.proof_attachment_id):
            raise ValueError("reference_number or proof is required")
        return self


class BudgetAdvanceTransferCreate(BaseSchema):
    """Transfer balance out of one advance into a new one."""

    to_budget_id: int
    to_employee_id: int | None = None
    transfer_date: date
    amount: Decimal = Field(..., gt=0)
    transfer_type: Literal["rollover", "reassignment", "reallocation"]
    reason: str = Field(..., min_length=1)
    settlement_due_date: date | None = None


class BudgetClaimAllocationResponse(BaseSchema):
    """Allocation row for a claim/advance link."""

    id: int
    advance_id: int
    advance_number: str
    claim_id: int
    allocated_amount: Decimal
    allocation_status: str
    released_reason: str | None
    created_at: datetime
    updated_at: datetime


class BudgetAdvanceReturnResponse(BaseSchema):
    """Return response."""

    id: int
    return_number: str
    advance_id: int
    return_date: date
    amount: Decimal
    return_method: str
    reference_number: str | None
    proof_text: str | None
    proof_attachment_id: int | None
    notes: str | None
    created_by_id: int
    created_at: datetime


class BudgetAdvanceTransferResponse(BaseSchema):
    """Transfer response."""

    id: int
    transfer_number: str
    from_advance_id: int
    from_advance_number: str
    to_budget_id: int
    to_budget_number: str
    to_employee_id: int
    to_employee_name: str | None = None
    transfer_date: date
    amount: Decimal
    transfer_type: str
    reason: str
    created_to_advance_id: int
    created_to_advance_number: str
    created_by_id: int
    created_at: datetime


class BudgetAdvanceResponse(BaseSchema):
    """Advance response with computed balances."""

    id: int
    advance_number: str
    budget_id: int
    budget_number: str
    budget_name: str
    employee_id: int
    employee_name: str
    issue_date: date
    amount_issued: Decimal
    payment_method: str
    reference_number: str | None
    proof_text: str | None
    proof_attachment_id: int | None
    notes: str | None
    source_type: str
    settlement_due_date: date
    status: str
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    reserved_amount: Decimal
    settled_amount: Decimal
    returned_amount: Decimal
    transferred_out_amount: Decimal
    open_balance: Decimal
    available_unreserved_amount: Decimal


class MyBudgetAvailableBalanceResponse(BaseSchema):
    """Budget availability for the current employee."""

    budget_id: int
    budget_number: str
    budget_name: str
    available_unreserved_total: Decimal

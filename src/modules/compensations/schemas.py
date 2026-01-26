"""Schemas for compensations (Expense Claims)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class ExpenseClaimResponse(BaseModel):
    """Schema for expense claim response."""

    id: int
    claim_number: str
    payment_id: int
    employee_id: int
    purpose_id: int
    amount: Decimal
    description: str
    expense_date: date
    status: str
    paid_amount: Decimal
    remaining_amount: Decimal
    auto_created_from_payment: bool
    related_procurement_payment_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApproveExpenseClaimRequest(BaseModel):
    """Schema for approving/rejecting an expense claim."""

    approve: bool
    reason: str | None = None

    model_config = {"from_attributes": True}


class CompensationPayoutCreate(BaseModel):
    """Schema for creating a payout."""

    employee_id: int
    payout_date: date
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., min_length=1, max_length=20)
    reference_number: str | None = Field(None, max_length=200)
    proof_text: str | None = None
    proof_attachment_id: int | None = None

    @model_validator(mode="after")
    def validate_proof(self):
        if not self.proof_text and not self.proof_attachment_id:
            raise ValueError("Proof is required: provide proof_text or proof_attachment_id")
        return self


class PayoutAllocationResponse(BaseModel):
    """Schema for payout allocation response."""

    id: int
    claim_id: int
    allocated_amount: Decimal

    model_config = {"from_attributes": True}


class CompensationPayoutResponse(BaseModel):
    """Schema for payout response."""

    id: int
    payout_number: str
    employee_id: int
    payout_date: date
    amount: Decimal
    payment_method: str
    reference_number: str | None
    proof_text: str | None
    proof_attachment_id: int | None
    created_at: datetime
    updated_at: datetime
    allocations: list[PayoutAllocationResponse] = []

    model_config = {"from_attributes": True}


class EmployeeBalanceResponse(BaseModel):
    """Schema for employee balance response."""

    employee_id: int
    total_approved: Decimal
    total_paid: Decimal
    balance: Decimal

    model_config = {"from_attributes": True}

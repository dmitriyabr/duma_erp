"""Schemas for compensations (Expense Claims)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExpenseClaimResponse(BaseModel):
    """Schema for expense claim response."""

    id: int
    claim_number: str
    payment_id: int | None
    fee_payment_id: int | None
    budget_id: int | None
    budget_number: str | None
    budget_name: str | None
    employee_id: int
    employee_name: str
    purpose_id: int
    amount: Decimal
    expense_amount: Decimal
    fee_amount: Decimal
    payee_name: str | None
    description: str
    rejection_reason: str | None
    edit_comment: str | None
    expense_date: date
    proof_text: str | None
    proof_attachment_id: int | None
    fee_proof_text: str | None
    fee_proof_attachment_id: int | None
    status: str
    paid_amount: Decimal
    remaining_amount: Decimal
    auto_created_from_payment: bool
    funding_source: str
    budget_funding_status: str
    related_procurement_payment_id: int | None
    created_at: datetime
    updated_at: datetime
    budget_allocations: list["ClaimBudgetAllocationResponse"] = []

    model_config = {"from_attributes": True}


class ExpenseClaimCreate(BaseModel):
    """Create out-of-pocket expense claim."""

    employee_id: int | None = None
    budget_id: int | None = None
    funding_source: Literal["personal_funds", "budget"] = "personal_funds"
    purpose_id: int
    amount: Decimal = Field(..., gt=0)
    payee_name: str | None = Field(None, max_length=300)
    description: str = Field(..., min_length=1)
    expense_date: date
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    fee_amount: Decimal | None = Field(None, ge=0)
    fee_proof_text: str | None = None
    fee_proof_attachment_id: int | None = None
    submit: bool = True

    @model_validator(mode="after")
    def validate_proof(self):
        if self.funding_source == "budget" and not self.budget_id:
            raise ValueError("budget_id is required when funding_source=budget")
        if self.submit and not self.proof_text and not self.proof_attachment_id:
            raise ValueError("Proof is required: provide proof_text or proof_attachment_id")
        if self.fee_amount and self.fee_amount > 0:
            if not self.fee_proof_text and not self.fee_proof_attachment_id:
                raise ValueError("Fee proof is required: provide fee_proof_text or fee_proof_attachment_id")
        return self


class ExpenseClaimUpdate(BaseModel):
    """Update out-of-pocket claim (draft only)."""

    employee_id: int | None = None
    budget_id: int | None = None
    funding_source: Literal["personal_funds", "budget"] | None = None
    purpose_id: int | None = None
    amount: Decimal | None = Field(None, gt=0)
    payee_name: str | None = Field(None, max_length=300)
    description: str | None = Field(None, min_length=1)
    expense_date: date | None = None
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    fee_amount: Decimal | None = Field(None, ge=0)
    fee_proof_text: str | None = None
    fee_proof_attachment_id: int | None = None
    submit: bool | None = None

    @model_validator(mode="after")
    def validate_proof(self):
        if self.submit is True and not self.proof_text and not self.proof_attachment_id:
            raise ValueError("Proof is required: provide proof_text or proof_attachment_id")
        if self.fee_amount and self.fee_amount > 0:
            if not self.fee_proof_text and not self.fee_proof_attachment_id:
                raise ValueError("Fee proof is required: provide fee_proof_text or fee_proof_attachment_id")
        return self


class ApproveExpenseClaimRequest(BaseModel):
    """Schema for approving/rejecting an expense claim."""

    approve: bool
    reason: str | None = None

    model_config = {"from_attributes": True}


class ClaimBudgetAllocationResponse(BaseModel):
    """Budget allocation visible on claim responses."""

    id: int
    advance_id: int
    advance_number: str
    allocated_amount: Decimal
    allocation_status: str
    released_reason: str | None


class SendToEditExpenseClaimRequest(BaseModel):
    """Schema for sending expense claim to edit."""

    comment: str = Field(..., min_length=1)

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


class EmployeeClaimTotalsResponse(BaseModel):
    """Claim totals for an employee (includes pending approval)."""

    employee_id: int
    total_submitted: Decimal
    count_submitted: int
    total_pending_approval: Decimal
    count_pending_approval: int
    total_approved: Decimal
    total_paid: Decimal
    balance: Decimal
    total_rejected: Decimal
    count_rejected: int

    model_config = {"from_attributes": True}


class EmployeeBalancesBatchRequest(BaseModel):
    """Request for batch employee balances."""

    employee_ids: list[int]


class EmployeeBalancesBatchResponse(BaseModel):
    """Response with list of employee balances."""

    balances: list[EmployeeBalanceResponse]


ExpenseClaimResponse.model_rebuild()

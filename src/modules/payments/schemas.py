"""Pydantic schemas for Payments module."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from src.shared.schemas.base import BaseSchema
from src.modules.payments.models import PaymentMethod, PaymentStatus


# --- Payment Schemas ---


class PaymentCreate(BaseSchema):
    """Schema for creating a payment. Reference or confirmation_attachment_id required."""

    student_id: int | None = None
    billing_account_id: int | None = None
    preferred_invoice_id: int | None = None
    amount: Decimal = Field(gt=0, description="Payment amount (must be positive)")
    payment_method: PaymentMethod
    payment_date: date
    reference: str | None = Field(None, max_length=100)
    confirmation_attachment_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_reference_or_attachment(self):
        if self.student_id is None and self.billing_account_id is None:
            raise ValueError("Either student_id or billing_account_id is required")
        if not self.reference and not self.confirmation_attachment_id:
            raise ValueError("Either reference or confirmation file (attachment) is required")
        return self


class PaymentUpdate(BaseSchema):
    """Schema for updating a payment (only pending payments)."""

    amount: Decimal | None = Field(None, gt=0)
    preferred_invoice_id: int | None = None
    payment_method: PaymentMethod | None = None
    payment_date: date | None = None
    reference: str | None = None
    notes: str | None = None


class PaymentResponse(BaseSchema):
    """Schema for payment response."""

    id: int
    payment_number: str
    receipt_number: str | None
    student_id: int
    student_name: str | None = None
    student_number: str | None = None
    billing_account_id: int | None = None
    billing_account_number: str | None = None
    billing_account_name: str | None = None
    preferred_invoice_id: int | None = None
    preferred_invoice_number: str | None = None
    amount: Decimal
    payment_method: str
    payment_date: date
    reference: str | None
    confirmation_attachment_id: int | None = None
    status: str
    notes: str | None
    refunded_amount: Decimal = Decimal("0.00")
    refundable_amount: Decimal = Decimal("0.00")
    refund_status: str = "none"
    received_by_id: int
    created_at: datetime
    updated_at: datetime


class PaymentRefundCreate(BaseSchema):
    """Schema for creating a refund."""

    amount: Decimal = Field(gt=0, description="Refund amount")
    refund_date: date
    refund_method: str | None = Field(None, max_length=20)
    reference_number: str | None = Field(None, max_length=200)
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    reason: str = Field(..., min_length=3)
    notes: str | None = None

    @model_validator(mode="after")
    def require_refund_proof(self):
        has_reference = bool((self.reference_number or "").strip())
        has_proof_text = bool((self.proof_text or "").strip())
        if not has_reference and not has_proof_text and self.proof_attachment_id is None:
            raise ValueError("Reference, proof text or confirmation file is required")
        return self


class PaymentRefundResponse(BaseSchema):
    """Schema for a refund response."""

    id: int
    refund_number: str | None = None
    payment_id: int | None = None
    billing_account_id: int
    amount: Decimal
    refund_date: date
    refund_method: str | None = None
    reference_number: str | None = None
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    reason: str
    notes: str | None
    refunded_by_id: int
    created_at: datetime
    updated_at: datetime


class PaymentRefundSourceResponse(BaseSchema):
    """Payment source attribution for an account-level refund."""

    id: int
    refund_id: int
    payment_id: int
    payment_number: str | None = None
    receipt_number: str | None = None
    amount: Decimal
    created_at: datetime


class RefundAllocationReversalRequest(BaseSchema):
    """Manual allocation impact override for an account-level refund."""

    allocation_id: int
    amount: Decimal = Field(gt=0)


class BillingAccountRefundCreate(PaymentRefundCreate):
    """Schema for creating a billing-account-level refund."""

    allocation_reversals: list[RefundAllocationReversalRequest] | None = None


class BillingAccountRefundPreviewRequest(BaseSchema):
    """Schema for previewing account-level refund impact."""

    amount: Decimal = Field(gt=0, description="Refund amount")
    refund_date: date | None = None
    allocation_reversals: list[RefundAllocationReversalRequest] | None = None


class RefundAllocationImpact(BaseSchema):
    """Invoice allocation impact caused by a refund."""

    allocation_id: int
    invoice_id: int
    invoice_number: str
    student_id: int
    student_name: str | None = None
    current_allocation_amount: Decimal
    reversal_amount: Decimal
    invoice_paid_total_before: Decimal
    invoice_amount_due_before: Decimal
    invoice_paid_total_after: Decimal
    invoice_amount_due_after: Decimal


class RefundPaymentSourceImpact(BaseSchema):
    """Payment source attribution preview."""

    payment_id: int
    payment_number: str
    receipt_number: str | None = None
    payment_date: date
    payment_amount: Decimal
    already_refunded_amount: Decimal
    source_amount: Decimal


class BillingAccountRefundPreview(BaseSchema):
    """Account-level refund preview response."""

    billing_account_id: int
    amount: Decimal
    completed_payments_total: Decimal
    posted_refunds_total: Decimal
    current_allocated_total: Decimal
    available_credit: Decimal
    refundable_total: Decimal
    amount_to_reopen: Decimal
    allocation_reversals: list[RefundAllocationImpact]
    payment_sources: list[RefundPaymentSourceImpact]


class BillingAccountRefundResponse(PaymentRefundResponse):
    """Detailed account-level refund response."""

    payment_sources: list[PaymentRefundSourceResponse] = Field(default_factory=list)
    allocation_reversals: list[RefundAllocationImpact] = Field(default_factory=list)


class PaymentFilters(BaseSchema):
    """Filters for listing payments."""

    student_id: int | None = None
    billing_account_id: int | None = None
    status: PaymentStatus | None = None
    payment_method: PaymentMethod | None = None
    search: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


# --- Credit Allocation Schemas ---


class AllocationCreate(BaseSchema):
    """Schema for manual credit allocation."""

    student_id: int | None = None
    billing_account_id: int | None = None
    invoice_id: int
    invoice_line_id: int | None = None
    amount: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def require_owner(self):
        if self.student_id is None and self.billing_account_id is None:
            raise ValueError("Either student_id or billing_account_id is required")
        return self


class AllocationResponse(BaseSchema):
    """Schema for allocation response."""

    id: int
    student_id: int
    billing_account_id: int | None = None
    invoice_id: int
    invoice_line_id: int | None
    amount: Decimal
    allocated_by_id: int
    created_at: datetime


class AutoAllocateRequest(BaseSchema):
    """Schema for auto-allocation request."""

    student_id: int | None = None
    billing_account_id: int | None = None
    max_amount: Decimal | None = Field(
        None, gt=0, description="Max amount to allocate (defaults to full balance)"
    )

    @model_validator(mode="after")
    def require_owner(self):
        if self.student_id is None and self.billing_account_id is None:
            raise ValueError("Either student_id or billing_account_id is required")
        return self


class AutoAllocateResult(BaseSchema):
    """Result of auto-allocation."""

    total_allocated: Decimal
    invoices_fully_paid: int
    invoices_partially_paid: int
    remaining_balance: Decimal
    allocations: list[AllocationResponse]


# --- Balance & Statement Schemas ---


class StudentBalance(BaseSchema):
    """Student billing summary.

    `available_balance` is the shared credit currently available on the linked billing account.
    `outstanding_debt` is always this student's own unpaid invoices.
    `balance` is student-facing net position. Shared credit is not attributed to one
    student, so balance only reflects that student's own debt.
    """

    student_id: int
    billing_account_id: int | None = None
    billing_account_number: str | None = None
    billing_account_name: str | None = None
    total_payments: Decimal
    total_refunded: Decimal = Decimal("0")
    total_allocated: Decimal
    available_balance: Decimal
    outstanding_debt: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")


class StudentBalancesBatchRequest(BaseSchema):
    """Request for batch student balances."""

    student_ids: list[int] = Field(..., min_length=0, max_length=500)


class StudentBalancesBatchResponse(BaseSchema):
    """Response with list of student balances."""

    balances: list[StudentBalance]


class StatementEntry(BaseSchema):
    """Single entry in a statement."""

    date: datetime
    entry_type: str
    description: str
    reference: str | None  # payment_number or invoice_number
    payment_id: int | None = None
    refund_id: int | None = None
    allocation_id: int | None = None
    invoice_id: int | None = None
    credit: Decimal | None  # payment (positive)
    debit: Decimal | None  # allocation (negative)
    balance: Decimal  # running balance


class StatementResponse(BaseSchema):
    """Student account statement."""

    student_id: int
    student_name: str
    billing_account_id: int | None = None
    billing_account_number: str | None = None
    billing_account_name: str | None = None
    period_from: date
    period_to: date
    opening_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    closing_balance: Decimal
    entries: list[StatementEntry]

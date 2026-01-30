"""Pydantic schemas for Payments module."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from src.shared.schemas.base import BaseSchema
from src.modules.payments.models import PaymentMethod, PaymentStatus


# --- Payment Schemas ---


class PaymentCreate(BaseSchema):
    """Schema for creating a payment. Reference or confirmation_attachment_id required."""

    student_id: int
    amount: Decimal = Field(gt=0, description="Payment amount (must be positive)")
    payment_method: PaymentMethod
    payment_date: date
    reference: str | None = Field(None, max_length=100)
    confirmation_attachment_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_reference_or_attachment(self):
        if not self.reference and not self.confirmation_attachment_id:
            raise ValueError("Either reference or confirmation file (attachment) is required")
        return self


class PaymentUpdate(BaseSchema):
    """Schema for updating a payment (only pending payments)."""

    amount: Decimal | None = Field(None, gt=0)
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
    amount: Decimal
    payment_method: str
    payment_date: date
    reference: str | None
    confirmation_attachment_id: int | None = None
    status: str
    notes: str | None
    received_by_id: int
    created_at: datetime
    updated_at: datetime


class PaymentFilters(BaseSchema):
    """Filters for listing payments."""

    student_id: int | None = None
    status: PaymentStatus | None = None
    payment_method: PaymentMethod | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


# --- Credit Allocation Schemas ---


class AllocationCreate(BaseSchema):
    """Schema for manual credit allocation."""

    student_id: int
    invoice_id: int
    invoice_line_id: int | None = None
    amount: Decimal = Field(gt=0)


class AllocationResponse(BaseSchema):
    """Schema for allocation response."""

    id: int
    student_id: int
    invoice_id: int
    invoice_line_id: int | None
    amount: Decimal
    allocated_by_id: int
    created_at: datetime


class AutoAllocateRequest(BaseSchema):
    """Schema for auto-allocation request."""

    student_id: int
    max_amount: Decimal | None = Field(
        None, gt=0, description="Max amount to allocate (defaults to full balance)"
    )


class AutoAllocateResult(BaseSchema):
    """Result of auto-allocation."""

    total_allocated: Decimal
    invoices_fully_paid: int
    invoices_partially_paid: int
    remaining_balance: Decimal
    allocations: list[AllocationResponse]


# --- Balance & Statement Schemas ---


class StudentBalance(BaseSchema):
    """Student's credit balance and net balance (credit − debt)."""

    student_id: int
    total_payments: Decimal
    total_allocated: Decimal
    available_balance: Decimal
    outstanding_debt: Decimal = Decimal("0")  # sum of amount_due on unpaid invoices
    balance: Decimal = Decimal("0")  # net: available_balance − outstanding_debt


class StudentBalancesBatchRequest(BaseSchema):
    """Request for batch student balances."""

    student_ids: list[int] = Field(..., min_length=0, max_length=500)


class StudentBalancesBatchResponse(BaseSchema):
    """Response with list of student balances."""

    balances: list[StudentBalance]


class StatementEntry(BaseSchema):
    """Single entry in a statement."""

    date: datetime
    description: str
    reference: str | None  # payment_number or invoice_number
    credit: Decimal | None  # payment (positive)
    debit: Decimal | None  # allocation (negative)
    balance: Decimal  # running balance


class StatementResponse(BaseSchema):
    """Student account statement."""

    student_id: int
    student_name: str
    period_from: date
    period_to: date
    opening_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    closing_balance: Decimal
    entries: list[StatementEntry]

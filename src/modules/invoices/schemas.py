"""Schemas for Invoices module."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from src.modules.invoices.models import InvoiceStatus, InvoiceType


# --- Invoice Line Schemas ---


class InvoiceLineCreate(BaseModel):
    """Schema for creating an invoice line."""

    kit_id: int
    quantity: int = Field(1, ge=1)
    # unit_price is auto-determined from kit, but can be overridden
    unit_price_override: Decimal | None = None
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)


class InvoiceLineResponse(BaseModel):
    """Schema for invoice line response."""

    id: int
    invoice_id: int
    kit_id: int
    description: str
    quantity: int
    unit_price: float
    line_total: float
    discount_amount: float
    net_amount: float
    paid_amount: float
    remaining_amount: float

    model_config = {"from_attributes": True}


class InvoiceLineDiscountUpdate(BaseModel):
    """Schema for updating line discount."""

    discount_amount: Decimal = Field(..., ge=0)


# --- Invoice Schemas ---


class InvoiceCreate(BaseModel):
    """Schema for creating an ad-hoc invoice."""

    student_id: int
    due_date: date | None = None
    notes: str | None = None
    lines: list[InvoiceLineCreate] = Field(default_factory=list)


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice (draft only)."""

    due_date: date | None = None
    notes: str | None = None


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    id: int
    invoice_number: str
    student_id: int
    student_name: str | None = None
    student_number: str | None = None
    term_id: int | None
    term_name: str | None = None
    invoice_type: str
    status: str
    issue_date: date | None
    due_date: date | None
    subtotal: float
    discount_total: float
    total: float
    paid_total: float
    amount_due: float
    notes: str | None
    created_by_id: int
    lines: list[InvoiceLineResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class InvoiceSummary(BaseModel):
    """Brief invoice summary for lists."""

    id: int
    invoice_number: str
    student_id: int
    student_name: str | None = None
    invoice_type: str
    status: str
    total: float
    paid_total: float
    amount_due: float
    issue_date: date | None
    due_date: date | None

    model_config = {"from_attributes": True}


# --- Term Invoice Generation ---


class TermInvoiceGenerationRequest(BaseModel):
    """Schema for generating term invoices."""

    term_id: int


class TermInvoiceGenerationForStudentRequest(BaseModel):
    """Schema for generating term invoices for a single student."""

    term_id: int
    student_id: int


class TermInvoiceGenerationResult(BaseModel):
    """Result of term invoice generation."""

    school_fee_invoices_created: int
    transport_invoices_created: int
    students_skipped: int  # Already had invoice for this term
    total_students_processed: int
    affected_student_ids: list[int] = []  # Students who got new Issued invoices (for auto-allocation)


# --- Issue Invoice ---


class IssueInvoiceRequest(BaseModel):
    """Schema for issuing an invoice."""

    due_date: date | None = None  # Override default +30 days


# --- Filters ---


class InvoiceFilters(BaseModel):
    """Filters for listing invoices."""

    student_id: int | None = None
    term_id: int | None = None
    invoice_type: InvoiceType | None = None
    status: InvoiceStatus | None = None
    search: str | None = None  # Search by invoice_number or student name
    page: int = Field(1, ge=1)
    limit: int = Field(100, ge=1, le=500)

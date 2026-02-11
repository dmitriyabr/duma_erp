"""Schemas for Procurement module (Purchase Orders)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.shared.schemas.base import BaseSchema


class PurchaseOrderLineCreate(BaseSchema):
    """Schema for creating a purchase order line."""

    item_id: int | None = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity_expected: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)


class PurchaseOrderCreate(BaseSchema):
    """Schema for creating a purchase order."""

    supplier_name: str = Field(..., min_length=1, max_length=300)
    supplier_contact: str | None = Field(None, max_length=200)
    purpose_id: int
    order_date: date | None = None
    expected_delivery_date: date | None = None
    track_to_warehouse: bool = True
    notes: str | None = None
    lines: list[PurchaseOrderLineCreate] = Field(..., min_length=1)


class PurchaseOrderLineUpdate(BaseSchema):
    """Schema for updating a purchase order line."""

    item_id: int | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    quantity_expected: int | None = Field(None, gt=0)
    unit_price: Decimal | None = Field(None, ge=0)


class PurchaseOrderUpdate(BaseSchema):
    """Schema for updating a purchase order (draft/ordered only)."""

    supplier_name: str | None = Field(None, min_length=1, max_length=300)
    supplier_contact: str | None = Field(None, max_length=200)
    purpose_id: int | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    track_to_warehouse: bool | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineUpdate] | None = None


class PurchaseOrderLineResponse(BaseSchema):
    """Schema for purchase order line response."""

    id: int
    item_id: int | None
    description: str
    quantity_expected: int
    quantity_cancelled: int
    quantity_received: int
    unit_price: Decimal
    line_total: Decimal
    line_order: int


class PurchaseOrderResponse(BaseSchema):
    """Schema for purchase order response."""

    id: int
    po_number: str
    supplier_name: str
    supplier_contact: str | None
    purpose_id: int
    status: str
    order_date: date
    expected_delivery_date: date | None
    track_to_warehouse: bool
    expected_total: Decimal
    received_value: Decimal
    paid_total: Decimal
    debt_amount: Decimal
    forecast_debt: Decimal
    notes: str | None
    cancelled_reason: str | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineResponse] = Field(default_factory=list)


class BulkUploadPOError(BaseSchema):
    """Single row error for bulk PO upload."""

    row: int
    message: str


class BulkUploadPOResponse(BaseSchema):
    """Response after bulk PO CSV upload (create PO from full CSV)."""

    po: dict | None = None  # {"id": int, "po_number": str} if success
    errors: list[BulkUploadPOError] = Field(default_factory=list)


class ParsedPOLine(BaseSchema):
    """One parsed PO line from CSV (for form preview)."""

    item_id: int | None = None
    description: str
    quantity_expected: int
    unit_price: Decimal


class ParsePOLinesResponse(BaseSchema):
    """Response after parsing PO lines from CSV (no PO created)."""

    lines: list[ParsedPOLine] = Field(default_factory=list)
    errors: list[BulkUploadPOError] = Field(default_factory=list)


class PurchaseOrderFilters(BaseSchema):
    """Filters for listing purchase orders."""

    status: str | None = None
    supplier_name: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


class CancelPurchaseOrderRequest(BaseSchema):
    """Schema for cancelling a purchase order."""

    reason: str = Field(..., min_length=1)


class RollbackPurchaseOrderReceivingRequest(BaseSchema):
    """Schema for rolling back receiving (SuperAdmin only)."""

    reason: str = Field(..., min_length=1)


class RollbackGRNRequest(BaseSchema):
    """Schema for rolling back an approved GRN (SuperAdmin only)."""

    reason: str = Field(..., min_length=1)


class PaymentPurposeCreate(BaseSchema):
    """Schema for creating a payment purpose."""

    name: str = Field(..., min_length=1, max_length=200)
    purpose_type: Literal["expense", "fee"] = "expense"


class PaymentPurposeUpdate(BaseSchema):
    """Schema for updating a payment purpose."""

    name: str | None = Field(None, min_length=1, max_length=200)
    is_active: bool | None = None
    purpose_type: Literal["expense", "fee"] | None = None


class PaymentPurposeResponse(BaseSchema):
    """Schema for payment purpose response."""

    id: int
    name: str
    is_active: bool
    purpose_type: str
    created_at: datetime
    updated_at: datetime


class ProcurementPaymentCreate(BaseSchema):
    """Schema for creating a procurement payment."""

    po_id: int | None = None
    purpose_id: int | None = None
    payee_name: str | None = Field(None, max_length=300)
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., min_length=1, max_length=20)
    reference_number: str | None = Field(None, max_length=200)
    proof_text: str | None = None
    proof_attachment_id: int | None = None
    company_paid: bool = True
    employee_paid_id: int | None = None

    @model_validator(mode="after")
    def validate_proof(self):
        if not self.proof_text and not self.proof_attachment_id:
            raise ValueError("Proof is required: provide proof_text or proof_attachment_id")
        return self


class ProcurementPaymentResponse(BaseSchema):
    """Schema for procurement payment response."""

    id: int
    payment_number: str
    po_id: int | None
    purpose_id: int
    purpose_name: str | None = None
    payee_name: str | None
    payment_date: date
    amount: Decimal
    payment_method: str
    reference_number: str | None
    proof_text: str | None
    proof_attachment_id: int | None
    company_paid: bool
    employee_paid_id: int | None
    status: str
    cancelled_reason: str | None
    cancelled_by_id: int | None
    cancelled_at: datetime | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class ProcurementPaymentFilters(BaseSchema):
    """Filters for listing procurement payments."""

    po_id: int | None = None
    purpose_id: int | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


class CancelProcurementPaymentRequest(BaseSchema):
    """Schema for cancelling a procurement payment."""

    reason: str = Field(..., min_length=1)


class GoodsReceivedLineCreate(BaseSchema):
    """Schema for creating a GRN line."""

    po_line_id: int
    quantity_received: int = Field(..., ge=0)  # Allow 0 for partial receiving


class GoodsReceivedNoteCreate(BaseSchema):
    """Schema for creating a GRN."""

    po_id: int
    received_date: date | None = None
    notes: str | None = None
    lines: list[GoodsReceivedLineCreate] = Field(..., min_length=1)


class GoodsReceivedLineResponse(BaseSchema):
    """Schema for GRN line response."""

    id: int
    po_line_id: int
    item_id: int | None
    quantity_received: int


class GoodsReceivedNoteResponse(BaseSchema):
    """Schema for GRN response."""

    id: int
    grn_number: str
    po_id: int
    status: str
    received_date: date
    received_by_id: int
    approved_by_id: int | None
    approved_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[GoodsReceivedLineResponse] = Field(default_factory=list)


class GoodsReceivedFilters(BaseSchema):
    """Filters for listing GRNs."""

    po_id: int | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=100)


class ProcurementDashboardResponse(BaseSchema):
    """Dashboard statistics for procurement."""

    total_supplier_debt: Decimal
    pending_grn_count: int

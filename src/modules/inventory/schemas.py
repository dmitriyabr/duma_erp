"""Schemas for Inventory module."""

from datetime import datetime
from enum import StrEnum
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from src.modules.inventory.models import RecipientType


# --- Stock Schemas ---


class StockResponse(BaseModel):
    """Schema for stock response."""

    id: int
    item_id: int
    item_sku: str | None = None
    item_name: str | None = None
    quantity_on_hand: int
    quantity_owed: int = 0
    quantity_available: int
    average_cost: Decimal

    model_config = {"from_attributes": True}


class RestockRowResponse(BaseModel):
    """Schema for restock planning row (sellable items only)."""

    item_id: int
    item_sku: str | None = None
    item_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None

    quantity_on_hand: int
    quantity_owed: int
    quantity_inbound: int
    quantity_net: int
    quantity_to_order: int


# --- Stock Movement Schemas ---


class ReceiveStockRequest(BaseModel):
    """Schema for receiving stock (incoming goods)."""

    item_id: int
    quantity: int = Field(..., gt=0, description="Quantity to receive (must be positive)")
    unit_cost: Decimal = Field(..., ge=0, decimal_places=2, description="Cost per unit")
    reference_type: str | None = Field(None, max_length=50, description="e.g., 'purchase_order'")
    reference_id: int | None = Field(None, description="ID of the reference document")
    notes: str | None = None


class AdjustStockRequest(BaseModel):
    """Schema for stock adjustment (correction, write-off)."""

    item_id: int
    quantity: int = Field(..., description="Adjustment quantity (positive to add, negative to remove)")
    reason: str = Field(..., min_length=1, description="Reason for adjustment")
    reference_type: str | None = Field(None, max_length=50)
    reference_id: int | None = None


class WriteOffReason(StrEnum):
    """Write-off reason categories."""

    DAMAGE = "damage"
    EXPIRED = "expired"
    LOST = "lost"
    OTHER = "other"


class WriteOffItem(BaseModel):
    """Write-off item entry."""

    item_id: int
    quantity: int = Field(..., gt=0, description="Quantity to write off")
    reason_category: WriteOffReason
    reason_detail: str | None = Field(None, max_length=500)


class WriteOffRequest(BaseModel):
    """Write-off request."""

    items: list[WriteOffItem] = Field(..., min_length=1)


class InventoryCountItem(BaseModel):
    """Inventory count entry."""

    item_id: int
    actual_quantity: int = Field(..., ge=0)


class InventoryCountRequest(BaseModel):
    """Inventory count request (bulk adjustment)."""

    items: list[InventoryCountItem] = Field(..., min_length=1)


class IssueStockRequest(BaseModel):
    """Schema for issuing stock (manual issue without reservation)."""

    item_id: int
    quantity: int = Field(..., gt=0, description="Quantity to issue (must be positive)")
    reference_type: str | None = Field(None, max_length=50, description="e.g., 'manual_issue'")
    reference_id: int | None = None
    notes: str | None = None


class StockMovementResponse(BaseModel):
    """Schema for stock movement response."""

    id: int
    stock_id: int
    item_id: int
    item_sku: str | None = None
    item_name: str | None = None
    movement_type: str
    quantity: int
    unit_cost: Decimal | None
    quantity_before: int
    quantity_after: int
    average_cost_before: Decimal
    average_cost_after: Decimal
    reference_type: str | None
    reference_id: int | None
    notes: str | None
    created_by_id: int
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WriteOffResponse(BaseModel):
    """Write-off response."""

    movements: list[StockMovementResponse]
    total: int


class InventoryCountResponse(BaseModel):
    """Inventory count response."""

    movements: list[StockMovementResponse]
    adjustments_created: int
    total_variance: int


# --- Issuance Schemas ---


class IssuanceItemCreate(BaseModel):
    """Schema for issuance item in issuance creation."""

    item_id: int
    quantity: int = Field(..., gt=0)


class InternalIssuanceCreate(BaseModel):
    """Schema for creating an internal issuance (to employee/student/other)."""

    recipient_type: RecipientType = Field(
        ..., description="Type of recipient: employee, student, or other"
    )
    recipient_id: int | None = Field(
        None,
        description="User ID for employee, student_id for student; omit for other",
    )
    recipient_name: str = Field(
        ..., min_length=1, max_length=200, description="Name of recipient for display"
    )
    items: list[IssuanceItemCreate] = Field(..., min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_recipient(self):
        if self.recipient_type in (RecipientType.EMPLOYEE, RecipientType.STUDENT):
            if self.recipient_id is None:
                raise ValueError("recipient_id is required for employee or student")
        elif self.recipient_type == RecipientType.OTHER:
            if self.recipient_id is not None:
                raise ValueError("recipient_id must be omitted for other")
        return self


class IssuanceItemResponse(BaseModel):
    """Schema for issuance item response."""

    id: int
    item_id: int
    item_sku: str | None = None
    item_name: str | None = None
    quantity: int
    unit_cost: Decimal

    model_config = {"from_attributes": True}


class IssuanceResponse(BaseModel):
    """Schema for issuance response."""

    id: int
    issuance_number: str
    issuance_type: str
    recipient_type: str
    recipient_id: int | None
    recipient_name: str
    reservation_id: int | None
    issued_by_id: int
    issued_by_name: str | None = None
    issued_at: datetime
    notes: str | None
    status: str
    items: list[IssuanceItemResponse] = []

    model_config = {"from_attributes": True}


class BulkUploadError(BaseModel):
    """Single row error in bulk upload."""

    row: int
    message: str


class BulkUploadResponse(BaseModel):
    """Response after bulk stock CSV upload."""

    rows_processed: int
    items_created: int
    errors: list[BulkUploadError] = []

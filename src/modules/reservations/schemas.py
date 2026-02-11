"""Schemas for Reservations module."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.reservations.models import ReservationStatus


class ReservationItemResponse(BaseModel):
    """Reservation item response."""

    id: int
    item_id: int
    item_sku: str | None = None
    item_name: str | None = None
    quantity_required: int
    quantity_issued: int

    model_config = {"from_attributes": True}


class ReservationResponse(BaseModel):
    """Reservation response."""

    id: int
    student_id: int
    student_name: str | None = None
    invoice_id: int
    invoice_line_id: int
    status: ReservationStatus
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    items: list[ReservationItemResponse]

    model_config = {"from_attributes": True}


class ReservationIssueItem(BaseModel):
    """Item issue request for reservation."""

    reservation_item_id: int
    quantity: int = Field(..., ge=0)  # Allow 0 for items not being issued


class ReservationIssueRequest(BaseModel):
    """Issue items for reservation."""

    items: list[ReservationIssueItem] = Field(..., min_length=1)
    notes: str | None = None


class ReservationCancelRequest(BaseModel):
    """Cancel reservation request."""

    reason: str | None = Field(None, max_length=500)


class ReservationConfigureComponentsAllocation(BaseModel):
    item_id: int
    quantity: int = Field(..., ge=1)


class ReservationConfigureComponentsComponent(BaseModel):
    allocations: list[ReservationConfigureComponentsAllocation] = Field(..., min_length=1)


class ReservationConfigureComponentsRequest(BaseModel):
    """Configure concrete components for an editable kit reservation.

    `components` must be provided in the same order as the kit's components.
    Each component contains `allocations` that must sum to the required quantity
    for that kit component (kit_item.quantity * invoice_line.quantity).
    Only variant components are changeable; fixed item components must match the kit.
    """

    components: list[ReservationConfigureComponentsComponent] = Field(..., min_length=1)

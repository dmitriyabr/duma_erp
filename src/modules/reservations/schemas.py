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
    quantity_reserved: int
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

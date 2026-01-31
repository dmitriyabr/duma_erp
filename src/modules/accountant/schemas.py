"""Pydantic schemas for Accountant module."""

from datetime import datetime

from pydantic import Field

from src.shared.schemas.base import BaseSchema


class AuditTrailEntryResponse(BaseSchema):
    """Single audit log entry for accountant view."""

    id: int
    user_id: int | None
    user_full_name: str | None
    action: str
    entity_type: str
    entity_id: int
    entity_identifier: str | None
    old_values: dict | None
    new_values: dict | None
    comment: str | None
    created_at: datetime

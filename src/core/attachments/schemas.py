"""Pydantic schemas for attachments."""

from datetime import datetime

from pydantic import BaseModel, Field


class AttachmentResponse(BaseModel):
    """Response after upload or get."""

    id: int
    file_name: str
    content_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base Pydantic schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class ErrorDetail(BaseSchema):
    """Error detail for a specific field."""

    field: str | None = None
    message: str


class SuccessResponse(BaseSchema, Generic[T]):
    """Standard success response wrapper."""

    success: bool = True
    data: T
    message: str | None = None


# Alias for cleaner API usage
ApiResponse = SuccessResponse


class ErrorResponse(BaseSchema):
    """Standard error response wrapper."""

    success: bool = False
    data: None = None
    message: str
    errors: list[ErrorDetail] = []


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    limit: int
    pages: int

    @classmethod
    def create(cls, items: list[T], total: int, page: int, limit: int) -> "PaginatedResponse[T]":
        pages = (total + limit - 1) // limit if limit > 0 else 0
        return cls(items=items, total=total, page=page, limit=limit, pages=pages)


class TimestampMixin(BaseSchema):
    """Mixin for created_at and updated_at fields."""

    created_at: datetime
    updated_at: datetime

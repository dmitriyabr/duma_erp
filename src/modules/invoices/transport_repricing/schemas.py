"""Reviewable whole-term transport recalculation."""

from decimal import Decimal

from pydantic import Field, field_validator

from src.shared.schemas import BaseSchema


class RepricingPreview(BaseSchema):
    invoice_id: int
    invoice_number: str
    student_name: str
    term_name: str
    zone_name: str
    price_before: Decimal
    price_after: Decimal
    discount_before: Decimal
    discount_after: Decimal
    total_before: Decimal
    total_after: Decimal
    paid_before: Decimal
    paid_after: Decimal
    due_before: Decimal
    due_after: Decimal
    credit_before: Decimal
    credit_after: Decimal
    released_credit: Decimal
    changed: bool
    preview_token: str = ""


class RepricingRequest(BaseSchema):
    preview_token: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A reason is required")
        return value.strip()

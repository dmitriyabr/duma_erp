"""Schemas for reports API (Admin/SuperAdmin)."""

from datetime import date
from decimal import Decimal

from src.shared.schemas.base import BaseSchema


class AgedReceivablesRow(BaseSchema):
    """One row in Aged Receivables report."""

    student_id: int
    student_name: str
    total: Decimal
    current: Decimal  # 0-30 days (not yet due + up to 30 days overdue)
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_90_plus: Decimal
    last_payment_date: date | None


class AgedReceivablesSummary(BaseSchema):
    """Summary totals for Aged Receivables."""

    total: Decimal
    current: Decimal  # 0-30 days
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_90_plus: Decimal


class AgedReceivablesResponse(BaseSchema):
    """Aged Receivables report response."""

    as_at_date: date
    rows: list[AgedReceivablesRow]
    summary: AgedReceivablesSummary

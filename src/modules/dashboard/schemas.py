"""Schemas for dashboard API (main page summary for Admin/SuperAdmin)."""

from decimal import Decimal

from src.shared.schemas.base import BaseSchema


class DashboardResponse(BaseSchema):
    """Summary data for main page: cards, key metrics, alerts."""

    # Overview cards
    active_students_count: int = 0
    total_revenue_this_year: Decimal = Decimal("0")
    this_term_revenue: Decimal = Decimal("0")
    this_term_invoiced: Decimal = Decimal("0")
    collection_rate_percent: float | None = None  # 0–100, None if no invoiced
    total_expenses_this_year: Decimal = Decimal("0")
    procurement_total_this_year: Decimal = Decimal("0")
    employee_compensations_this_year: Decimal = Decimal("0")
    # Cash balance: not tracked separately; can be derived or 0 for MVP
    cash_balance: Decimal = Decimal("0")

    # Key metrics (4 cards)
    student_debts_total: Decimal = Decimal("0")
    student_debts_count: int = 0
    supplier_debt: Decimal = Decimal("0")
    credit_balances_total: Decimal = Decimal("0")
    pending_claims_count: int = 0
    pending_claims_amount: Decimal = Decimal("0")
    pending_grn_count: int = 0

    # Context
    active_term_id: int | None = None
    active_term_display_name: str | None = None
    current_year: int = 0

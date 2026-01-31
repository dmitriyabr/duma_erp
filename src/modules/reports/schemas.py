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


class StudentFeesRow(BaseSchema):
    """One row in Student Fees Summary by Term (per grade)."""

    grade_id: int
    grade_name: str
    students_count: int
    total_invoiced: Decimal
    total_paid: Decimal
    balance: Decimal
    rate_percent: float | None  # collection rate 0-100, None if no invoiced


class StudentFeesSummary(BaseSchema):
    """Total row for Student Fees Summary."""

    students_count: int
    total_invoiced: Decimal
    total_paid: Decimal
    balance: Decimal
    rate_percent: float | None


class StudentFeesResponse(BaseSchema):
    """Student Fees Summary by Term response."""

    term_id: int
    term_display_name: str
    grade_id: int | None  # if filter applied
    rows: list[StudentFeesRow]
    summary: StudentFeesSummary


# --- Profit & Loss ---

class ProfitLossRevenueLine(BaseSchema):
    """Revenue line by type (e.g. School Fee, Transport)."""

    label: str
    amount: Decimal


class ProfitLossExpenseLine(BaseSchema):
    """Expense line (e.g. Procurement, Compensations)."""

    label: str
    amount: Decimal


class ProfitLossResponse(BaseSchema):
    """Profit & Loss statement for a date range."""

    date_from: date
    date_to: date
    revenue_lines: list[ProfitLossRevenueLine]
    gross_revenue: Decimal
    total_discounts: Decimal
    net_revenue: Decimal
    expense_lines: list[ProfitLossExpenseLine]
    total_expenses: Decimal
    net_profit: Decimal
    profit_margin_percent: float | None  # net_profit / net_revenue * 100, None if no revenue


# --- Cash Flow ---

class CashFlowInflowLine(BaseSchema):
    """Cash inflow line (e.g. by payment method)."""

    label: str
    amount: Decimal


class CashFlowOutflowLine(BaseSchema):
    """Cash outflow line."""

    label: str
    amount: Decimal


class CashFlowResponse(BaseSchema):
    """Cash flow report for a date range."""

    date_from: date
    date_to: date
    opening_balance: Decimal
    inflow_lines: list[CashFlowInflowLine]
    total_inflows: Decimal
    outflow_lines: list[CashFlowOutflowLine]
    total_outflows: Decimal
    net_cash_flow: Decimal
    closing_balance: Decimal


# --- Balance Sheet ---

class BalanceSheetAssetLine(BaseSchema):
    """Asset line."""

    label: str
    amount: Decimal


class BalanceSheetLiabilityLine(BaseSchema):
    """Liability line."""

    label: str
    amount: Decimal


class BalanceSheetResponse(BaseSchema):
    """Balance sheet as at a date."""

    as_at_date: date
    asset_lines: list[BalanceSheetAssetLine]
    total_assets: Decimal
    liability_lines: list[BalanceSheetLiabilityLine]
    total_liabilities: Decimal
    net_equity: Decimal
    debt_to_asset_percent: float | None  # total_liabilities / total_assets * 100
    current_ratio: float | None  # current_assets / current_liabilities

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
    monthly: dict[str, Decimal] | None = None  # YYYY-MM -> amount when breakdown=monthly


class ProfitLossExpenseLine(BaseSchema):
    """Expense line (e.g. Procurement, Compensations)."""

    label: str
    amount: Decimal
    monthly: dict[str, Decimal] | None = None  # YYYY-MM -> amount when breakdown=monthly


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
    months: list[str] | None = None  # YYYY-MM when breakdown=monthly
    gross_revenue_monthly: dict[str, Decimal] | None = None
    total_discounts_monthly: dict[str, Decimal] | None = None
    net_revenue_monthly: dict[str, Decimal] | None = None
    total_expenses_monthly: dict[str, Decimal] | None = None
    net_profit_monthly: dict[str, Decimal] | None = None
    profit_margin_percent_monthly: dict[str, float] | None = None  # when breakdown=monthly


# --- Cash Flow ---

class CashFlowInflowLine(BaseSchema):
    """Cash inflow line (e.g. by payment method)."""

    label: str
    amount: Decimal
    monthly: dict[str, Decimal] | None = None  # YYYY-MM when breakdown=monthly


class CashFlowOutflowLine(BaseSchema):
    """Cash outflow line."""

    label: str
    amount: Decimal
    monthly: dict[str, Decimal] | None = None  # YYYY-MM when breakdown=monthly


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
    months: list[str] | None = None  # YYYY-MM when breakdown=monthly
    total_inflows_monthly: dict[str, Decimal] | None = None
    total_outflows_monthly: dict[str, Decimal] | None = None
    closing_balance_monthly: dict[str, Decimal] | None = None  # cumulative closing per month end


# --- Balance Sheet ---

class BalanceSheetAssetLine(BaseSchema):
    """Asset line."""

    label: str
    amount: Decimal
    monthly: dict[str, Decimal] | None = None  # YYYY-MM when breakdown=monthly (as at month end)


class BalanceSheetLiabilityLine(BaseSchema):
    """Liability line."""

    label: str
    amount: Decimal
    monthly: dict[str, Decimal] | None = None  # YYYY-MM when breakdown=monthly (as at month end)


class BalanceSheetResponse(BaseSchema):
    """Balance sheet as at a date."""

    as_at_date: date
    asset_lines: list[BalanceSheetAssetLine]
    total_assets: Decimal
    liability_lines: list[BalanceSheetLiabilityLine]
    total_liabilities: Decimal
    net_equity: Decimal
    months: list[str] | None = None  # YYYY-MM when breakdown=monthly (date_from/date_to range)
    total_assets_monthly: dict[str, Decimal] | None = None
    total_liabilities_monthly: dict[str, Decimal] | None = None
    net_equity_monthly: dict[str, Decimal] | None = None
    debt_to_asset_percent: float | None  # total_liabilities / total_assets * 100
    current_ratio: float | None  # current_assets / current_liabilities
    debt_to_asset_percent_monthly: dict[str, float] | None = None  # when breakdown=monthly
    current_ratio_monthly: dict[str, float] | None = None  # when breakdown=monthly


# --- Students: Collection Rate Trend ---

class CollectionRateMonthRow(BaseSchema):
    """One month in Collection Rate Trend."""

    year_month: str  # YYYY-MM
    label: str  # e.g. "Jan 2026"
    total_invoiced: Decimal
    total_paid: Decimal
    rate_percent: float | None


class CollectionRateResponse(BaseSchema):
    """Collection rate % over last N months (e.g. 12)."""

    rows: list[CollectionRateMonthRow]
    average_rate_percent: float | None
    target_rate_percent: float | None  # optional target line, e.g. 90


# --- Students: Discount Analysis ---

class DiscountAnalysisRow(BaseSchema):
    """Discount by reason/type."""

    reason_id: int | None
    reason_code: str | None
    reason_name: str
    students_count: int
    total_amount: Decimal
    avg_per_student: Decimal | None
    percent_of_revenue: float | None


class DiscountAnalysisSummary(BaseSchema):
    """Totals for discount analysis."""

    students_count: int
    total_discount_amount: Decimal
    total_revenue: Decimal
    percent_of_revenue: float | None


class DiscountAnalysisResponse(BaseSchema):
    """Discount analysis for a period."""

    date_from: date
    date_to: date
    rows: list[DiscountAnalysisRow]
    summary: DiscountAnalysisSummary


# --- Students: Top Debtors ---

class TopDebtorRow(BaseSchema):
    """One student in Top Debtors report."""

    student_id: int
    student_name: str
    grade_name: str
    total_debt: Decimal
    invoice_count: int
    oldest_due_date: date | None


class TopDebtorsResponse(BaseSchema):
    """Top N students by debt amount."""

    as_at_date: date
    limit: int
    rows: list[TopDebtorRow]
    total_debt: Decimal


# --- Procurement & Inventory ---

class ProcurementSummaryRow(BaseSchema):
    """One supplier row in Procurement Summary."""

    supplier_name: str
    po_count: int
    total_amount: Decimal
    paid: Decimal
    outstanding: Decimal
    status: str  # "ok" | "partial"


class ProcurementSummaryOutstanding(BaseSchema):
    """Outstanding debt by age bucket (0-30, 31-60, 61+ days since order)."""

    current_0_30: Decimal
    bucket_31_60: Decimal
    bucket_61_plus: Decimal


class ProcurementSummaryResponse(BaseSchema):
    """Procurement Summary report for a period."""

    date_from: date
    date_to: date
    rows: list[ProcurementSummaryRow]
    total_po_count: int
    total_amount: Decimal
    total_paid: Decimal
    total_outstanding: Decimal
    outstanding_breakdown: ProcurementSummaryOutstanding


class InventoryValuationRow(BaseSchema):
    """One category row in Inventory Valuation."""

    category_id: int
    category_name: str
    items_count: int
    quantity: int
    unit_cost_avg: Decimal | None
    total_value: Decimal
    turnover: float | None  # optional, None if not computed


class InventoryValuationResponse(BaseSchema):
    """Inventory Valuation as at date."""

    as_at_date: date
    rows: list[InventoryValuationRow]
    total_items: int
    total_quantity: int
    total_value: Decimal


class LowStockAlertRow(BaseSchema):
    """One item in Low Stock Alert."""

    item_id: int
    item_name: str
    sku_code: str
    current: int
    min_level: int  # 0 if not set in DB
    status: str  # "out" | "low" | "ok"
    suggested_order: int | None  # optional


class LowStockAlertResponse(BaseSchema):
    """Low Stock Alert report (items at or below min level)."""

    rows: list[LowStockAlertRow]
    total_low_count: int


class StockMovementRow(BaseSchema):
    """One row in Stock Movement report."""

    movement_id: int
    movement_date: date
    movement_type: str
    item_id: int
    item_name: str
    quantity: int  # signed
    ref_display: str | None  # e.g. GRN-2026-45, ISS-2026-001
    created_by_name: str
    balance_after: int


class StockMovementResponse(BaseSchema):
    """Stock Movement report for a period."""

    date_from: date
    date_to: date
    rows: list[StockMovementRow]


# --- Compensations ---

class CompensationSummaryRow(BaseSchema):
    """One employee row in Compensation Summary."""

    employee_id: int
    employee_name: str
    claims_count: int
    total_amount: Decimal
    approved_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal


class CompensationSummaryTotals(BaseSchema):
    """Summary totals for Compensation Summary."""

    total_claims: int
    total_amount: Decimal
    total_approved: Decimal
    total_paid: Decimal
    total_pending: Decimal
    pending_approval_count: int
    pending_approval_amount: Decimal
    approved_unpaid_count: int
    approved_unpaid_amount: Decimal


class CompensationSummaryResponse(BaseSchema):
    """Compensation Summary report for a period."""

    date_from: date
    date_to: date
    rows: list[CompensationSummaryRow]
    summary: CompensationSummaryTotals


class ExpenseClaimsByCategoryRow(BaseSchema):
    """One category/purpose row in Expense Claims by Category."""

    purpose_id: int
    purpose_name: str
    amount: Decimal
    claims_count: int
    percent_of_total: float | None


class ExpenseClaimsByCategoryResponse(BaseSchema):
    """Expense Claims by Category (for pie chart) for a period."""

    date_from: date
    date_to: date
    rows: list[ExpenseClaimsByCategoryRow]
    total_amount: Decimal


# --- Analytics ---

class RevenueTrendRow(BaseSchema):
    """One year in Revenue per Student trend."""

    year: int
    label: str  # e.g. "2025/2026"
    total_revenue: Decimal
    students_count: int
    avg_revenue_per_student: Decimal | None


class RevenueTrendResponse(BaseSchema):
    """Revenue per student trend over N years."""

    rows: list[RevenueTrendRow]
    growth_percent: float | None  # year-over-year from first to last
    years_included: int


class PaymentMethodDistributionRow(BaseSchema):
    """One payment method in distribution."""

    payment_method: str
    label: str  # e.g. "M-Pesa"
    amount: Decimal
    percent_of_total: float | None


class PaymentMethodDistributionResponse(BaseSchema):
    """Payment method distribution for a period (student payments)."""

    date_from: date
    date_to: date
    rows: list[PaymentMethodDistributionRow]
    total_amount: Decimal


class TermComparisonMetric(BaseSchema):
    """One metric in term-over-term comparison."""

    name: str
    term1_value: str | float | int  # display value
    term2_value: str | float | int
    change_abs: str | float | None
    change_percent: float | None


class TermComparisonResponse(BaseSchema):
    """Term-over-term comparison (two terms)."""

    term1_id: int
    term1_display_name: str
    term2_id: int
    term2_display_name: str
    metrics: list[TermComparisonMetric]


class KpisResponse(BaseSchema):
    """KPIs & key metrics for a period (year or term)."""

    period_type: str  # "year" | "term"
    year: int | None
    term_id: int | None
    term_display_name: str | None
    active_students_count: int
    total_revenue: Decimal
    total_invoiced: Decimal
    collection_rate_percent: float | None
    total_expenses: Decimal
    student_debt: Decimal
    supplier_debt: Decimal
    pending_claims_amount: Decimal

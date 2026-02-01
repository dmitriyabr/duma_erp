"""API for reports (Admin/SuperAdmin only)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.reports.schemas import (
    AgedReceivablesResponse,
    StudentFeesResponse,
    ProfitLossResponse,
    CashFlowResponse,
    BalanceSheetResponse,
    CollectionRateResponse,
    DiscountAnalysisResponse,
    TopDebtorsResponse,
    ProcurementSummaryResponse,
    InventoryValuationResponse,
    LowStockAlertResponse,
    StockMovementResponse,
    CompensationSummaryResponse,
    ExpenseClaimsByCategoryResponse,
    RevenueTrendResponse,
    PaymentMethodDistributionResponse,
    TermComparisonResponse,
    KpisResponse,
)
from src.modules.reports.service import ReportsService
from src.shared.schemas.base import ApiResponse

router = APIRouter(prefix="/reports", tags=["Reports"])

ReportsUser = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))


@router.get(
    "/aged-receivables",
    response_model=ApiResponse[AgedReceivablesResponse],
)
async def get_aged_receivables(
    as_at_date: date | None = Query(
        None,
        description="Report date (default: today). Aging = as_at_date - due_date.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Aged Receivables: student debts by aging bucket (current 0-30, 31-60, 61-90, 90+ days overdue).

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.aged_receivables(as_at_date=as_at_date)
    return ApiResponse(data=AgedReceivablesResponse(**data))


@router.get(
    "/student-fees",
    response_model=ApiResponse[StudentFeesResponse],
)
async def get_student_fees(
    term_id: int = Query(..., description="Term ID (required)."),
    grade_id: int | None = Query(None, description="Filter by grade (optional)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Student Fees Summary by Term: per-grade table (students count, total invoiced, paid, balance, rate).

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.student_fees_summary(term_id=term_id, grade_id=grade_id)
    return ApiResponse(data=StudentFeesResponse(**data))


@router.get(
    "/profit-loss",
    response_model=ApiResponse[ProfitLossResponse],
)
async def get_profit_loss(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    breakdown: str | None = Query(
        None,
        description="Pass 'monthly' for per-month columns in the response.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Profit & Loss: revenue by type, less discounts, expenses (procurement + compensations).

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.profit_loss(
        date_from=date_from,
        date_to=date_to,
        breakdown_monthly=(breakdown == "monthly"),
    )
    return ApiResponse(data=ProfitLossResponse(**data))


@router.get(
    "/cash-flow",
    response_model=ApiResponse[CashFlowResponse],
)
async def get_cash_flow(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    payment_method: str | None = Query(
        None,
        description="Filter student inflows by method: mpesa, bank_transfer, or omit for all.",
    ),
    breakdown: str | None = Query(
        None,
        description="Pass 'monthly' for per-month columns in the response.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Cash flow: opening balance, inflows (student payments), outflows, closing balance.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.cash_flow(
        date_from=date_from,
        date_to=date_to,
        payment_method=payment_method,
        breakdown_monthly=(breakdown == "monthly"),
    )
    return ApiResponse(data=CashFlowResponse(**data))


@router.get(
    "/balance-sheet",
    response_model=ApiResponse[BalanceSheetResponse],
)
async def get_balance_sheet(
    as_at_date: date | None = Query(
        None,
        description="Report date (default: today).",
    ),
    date_from: date | None = Query(
        None,
        description="Start of range for monthly breakdown (use with date_to and breakdown=monthly).",
    ),
    date_to: date | None = Query(
        None,
        description="End of range for monthly breakdown (use with date_from and breakdown=monthly).",
    ),
    breakdown: str | None = Query(
        None,
        description="Pass 'monthly' with date_from/date_to for per-month columns (as at each month end).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Balance sheet as at date: assets, liabilities, net equity, ratios.

    Access: SuperAdmin, Admin only.
    """
    as_at = as_at_date or date.today()
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.balance_sheet(
        as_at_date=as_at,
        date_from=date_from,
        date_to=date_to,
        breakdown_monthly=(breakdown == "monthly" and bool(date_from and date_to)),
    )
    return ApiResponse(data=BalanceSheetResponse(**data))


@router.get(
    "/collection-rate",
    response_model=ApiResponse[CollectionRateResponse],
)
async def get_collection_rate(
    months: int = Query(12, ge=1, le=24, description="Number of months (default 12)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Collection rate trend: rate % per month over last N months (invoiced vs paid in month).

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.collection_rate_trend(months=months)
    return ApiResponse(data=CollectionRateResponse(**data))


@router.get(
    "/discount-analysis",
    response_model=ApiResponse[DiscountAnalysisResponse],
)
async def get_discount_analysis(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Discount analysis by reason: students count, total amount, avg per student, % of revenue.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.discount_analysis(date_from=date_from, date_to=date_to)
    return ApiResponse(data=DiscountAnalysisResponse(**data))


@router.get(
    "/top-debtors",
    response_model=ApiResponse[TopDebtorsResponse],
)
async def get_top_debtors(
    as_at_date: date | None = Query(None, description="Report date (default: today)."),
    limit: int = Query(20, ge=1, le=100, description="Max number of students (default 20)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Top N students by debt amount.

    Access: SuperAdmin, Admin only.
    """
    as_at = as_at_date or date.today()
    service = ReportsService(db)
    data = await service.top_debtors(as_at_date=as_at, limit=limit)
    return ApiResponse(data=TopDebtorsResponse(**data))


@router.get(
    "/procurement-summary",
    response_model=ApiResponse[ProcurementSummaryResponse],
)
async def get_procurement_summary(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    supplier_name: str | None = Query(None, description="Filter by supplier name (optional)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Procurement Summary: by supplier, PO count, total/paid/outstanding, outstanding by age.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.procurement_summary(
        date_from=date_from,
        date_to=date_to,
        supplier_name=supplier_name,
    )
    return ApiResponse(data=ProcurementSummaryResponse(**data))


@router.get(
    "/inventory-valuation",
    response_model=ApiResponse[InventoryValuationResponse],
)
async def get_inventory_valuation(
    as_at_date: date | None = Query(None, description="Report date (default: today)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Inventory Valuation as at date: by category (items, quantity, value).

    Access: SuperAdmin, Admin only.
    """
    as_at = as_at_date or date.today()
    service = ReportsService(db)
    data = await service.inventory_valuation(as_at_date=as_at)
    return ApiResponse(data=InventoryValuationResponse(**data))


@router.get(
    "/low-stock-alert",
    response_model=ApiResponse[LowStockAlertResponse],
)
async def get_low_stock_alert(
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Low Stock Alert: items at or below min level (out of stock or low).

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.low_stock_alert()
    return ApiResponse(data=LowStockAlertResponse(**data))


@router.get(
    "/stock-movement",
    response_model=ApiResponse[StockMovementResponse],
)
async def get_stock_movement(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    movement_type: str | None = Query(
        None,
        description="Filter by type: receipt, issue, adjustment, etc. (optional).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Stock Movement report: movements in period with item, ref, user, balance.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.stock_movement_report(
        date_from=date_from,
        date_to=date_to,
        movement_type=movement_type,
    )
    return ApiResponse(data=StockMovementResponse(**data))


@router.get(
    "/compensation-summary",
    response_model=ApiResponse[CompensationSummaryResponse],
)
async def get_compensation_summary(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    status: str | None = Query(
        None,
        description="Filter by claim status: draft, pending_approval, approved, rejected, partially_paid, paid (optional).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Compensation Summary: by employee, claims count, total/approved/paid/pending.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.compensation_summary(
        date_from=date_from,
        date_to=date_to,
        status=status,
    )
    return ApiResponse(data=CompensationSummaryResponse(**data))


@router.get(
    "/expense-claims-by-category",
    response_model=ApiResponse[ExpenseClaimsByCategoryResponse],
)
async def get_expense_claims_by_category(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Expense Claims by Category (purpose): amount and count per category, percent of total.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.expense_claims_by_category(
        date_from=date_from,
        date_to=date_to,
    )
    return ApiResponse(data=ExpenseClaimsByCategoryResponse(**data))


@router.get(
    "/revenue-trend",
    response_model=ApiResponse[RevenueTrendResponse],
)
async def get_revenue_trend(
    years: int = Query(3, ge=1, le=10, description="Number of years (default 3)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Revenue per student trend over last N years.

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.revenue_trend(years=years)
    return ApiResponse(data=RevenueTrendResponse(**data))


@router.get(
    "/payment-method-distribution",
    response_model=ApiResponse[PaymentMethodDistributionResponse],
)
async def get_payment_method_distribution(
    date_from: date = Query(..., description="Start date (inclusive)."),
    date_to: date = Query(..., description="End date (inclusive)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Payment method distribution for student payments in period.

    Access: SuperAdmin, Admin only.
    """
    if date_from > date_to:
        raise HTTPException(400, "date_from must be <= date_to")
    service = ReportsService(db)
    data = await service.payment_method_distribution(
        date_from=date_from,
        date_to=date_to,
    )
    return ApiResponse(data=PaymentMethodDistributionResponse(**data))


@router.get(
    "/term-comparison",
    response_model=ApiResponse[TermComparisonResponse],
)
async def get_term_comparison(
    term1_id: int = Query(..., description="First term ID."),
    term2_id: int = Query(..., description="Second term ID."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Term-over-term comparison: students, invoiced, collected, rate, avg fee, discounts.

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.term_comparison(term1_id=term1_id, term2_id=term2_id)
    return ApiResponse(data=TermComparisonResponse(**data))


@router.get(
    "/kpis",
    response_model=ApiResponse[KpisResponse],
)
async def get_kpis(
    year: int | None = Query(None, description="Calendar year (optional; default current)."),
    term_id: int | None = Query(None, description="Term ID (optional; overrides year)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    KPIs & key metrics for a period (year or term).

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.kpis_report(year=year, term_id=term_id)
    return ApiResponse(data=KpisResponse(**data))

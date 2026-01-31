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
    data = await service.profit_loss(date_from=date_from, date_to=date_to)
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
    db: AsyncSession = Depends(get_db),
    current_user: User = ReportsUser,
):
    """
    Balance sheet as at date: assets, liabilities, net equity, ratios.

    Access: SuperAdmin, Admin only.
    """
    as_at = as_at_date or date.today()
    service = ReportsService(db)
    data = await service.balance_sheet(as_at_date=as_at)
    return ApiResponse(data=BalanceSheetResponse(**data))

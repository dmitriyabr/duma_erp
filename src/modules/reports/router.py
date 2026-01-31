"""API for reports (Admin/SuperAdmin only)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.reports.schemas import AgedReceivablesResponse
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
    Aged Receivables: student debts by aging bucket (current, 1-30, 31-60, 61-90, 90+ days overdue).

    Access: SuperAdmin, Admin only.
    """
    service = ReportsService(db)
    data = await service.aged_receivables(as_at_date=as_at_date)
    return ApiResponse(data=AgedReceivablesResponse(**data))

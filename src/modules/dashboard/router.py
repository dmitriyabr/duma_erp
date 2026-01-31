"""API for dashboard summary (main page, Admin/SuperAdmin only)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.dashboard.schemas import DashboardResponse
from src.modules.dashboard.service import DashboardService
from src.shared.schemas.base import ApiResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Only Admin and SuperAdmin see dashboard summary (cards, metrics, alerts)
DashboardUser = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))


@router.get(
    "",
    response_model=ApiResponse[DashboardResponse],
)
async def get_dashboard(
    period: str | None = Query(
        None,
        description="Reserved: current_term | this_year. Default: active term + this year.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = DashboardUser,
):
    """
    Get dashboard summary for main page: cards, key metrics, alerts.

    Access: SuperAdmin, Admin only. User and Accountant get 403.
    """
    service = DashboardService(db)
    # period unused for now; we always use active term + current year
    data = await service.get_summary()
    return ApiResponse(data=DashboardResponse(**data))

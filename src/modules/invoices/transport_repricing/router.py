"""Whole-term transport recalculation for school administrators."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.invoices.transport_repricing.schemas import RepricingPreview, RepricingRequest
from src.modules.invoices.transport_repricing.service import TransportRepricingService
from src.shared.schemas.base import ApiResponse

router = APIRouter()


@router.post(
    "/{invoice_id}/recalculate-transport/preview", response_model=ApiResponse[RepricingPreview]
)
async def preview_repricing(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    return ApiResponse(
        data=await TransportRepricingService(
            db, actor_is_super_admin=user.role == UserRole.SUPER_ADMIN
        ).preview(invoice_id)
    )


@router.post("/{invoice_id}/recalculate-transport", response_model=ApiResponse[RepricingPreview])
async def apply_repricing(
    invoice_id: int,
    data: RepricingRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    return ApiResponse(
        data=await TransportRepricingService(
            db, actor_is_super_admin=user.role == UserRole.SUPER_ADMIN
        ).apply(invoice_id, data, user.id),
        message="Transport recalculated for the whole term",
    )

"""SuperAdmin-only payment correction endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.payments.transfers.schemas import (
    TransferPreview,
    TransferPreviewRequest,
    TransferRequest,
)
from src.modules.payments.transfers.service import PaymentTransferService
from src.shared.schemas.base import ApiResponse

router = APIRouter()


@router.post("/{payment_id}/transfer/preview", response_model=ApiResponse[TransferPreview])
async def preview_transfer(
    payment_id: int,
    data: TransferPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    return ApiResponse(
        data=await PaymentTransferService(db).preview(payment_id, data.target_student_id)
    )


@router.post("/{payment_id}/transfer", response_model=ApiResponse[TransferPreview])
async def transfer_payment(
    payment_id: int,
    data: TransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    result = await PaymentTransferService(db).transfer(payment_id, data, current_user.id)
    return ApiResponse(data=result, message="Payment transferred successfully")

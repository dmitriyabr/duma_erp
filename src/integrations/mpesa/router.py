from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.integrations.mpesa.schemas import (
    MpesaC2BConfirmationPayload,
    MpesaC2BResponse,
    MpesaC2BEventResponse,
    MpesaC2BValidationPayload,
    MpesaLinkEventRequest,
)
from src.integrations.mpesa.service import MpesaC2BService
from src.modules.payments.schemas import PaymentResponse
from src.modules.payments.service import PaymentService
from src.shared.schemas.base import ApiResponse, PaginatedResponse


router = APIRouter(prefix="/mpesa", tags=["M-Pesa"])


@router.post("/c2b/validation/{token}", response_model=MpesaC2BResponse)
async def mpesa_c2b_validation(
    token: str,
    payload: MpesaC2BValidationPayload,
    db: AsyncSession = Depends(get_db),
):
    service = MpesaC2BService(db)
    if not service.verify_webhook_token(token):
        # Avoid exposing endpoint existence when token isn't configured/mismatched.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    ok = await service.validate_bill_ref(payload)
    # MVP default: accept even if unmatched; confirmation handler will persist unmatched and allow manual handling.
    if ok:
        return MpesaC2BResponse(ResultCode=0, ResultDesc="Accepted")
    return MpesaC2BResponse(ResultCode=0, ResultDesc="Accepted (unmatched)")


@router.post("/c2b/confirmation/{token}", response_model=MpesaC2BResponse)
async def mpesa_c2b_confirmation(
    token: str,
    payload: MpesaC2BConfirmationPayload,
    db: AsyncSession = Depends(get_db),
):
    service = MpesaC2BService(db)
    if not service.verify_webhook_token(token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await service.process_confirmation(payload)
    return MpesaC2BResponse(ResultCode=0, ResultDesc="Accepted")


@router.get(
    "/c2b/events/unmatched",
    response_model=ApiResponse[PaginatedResponse[MpesaC2BEventResponse]],
)
async def list_unmatched_mpesa_events(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = MpesaC2BService(db)
    events, total = await service.list_unmatched_events(page=page, limit=limit)
    return ApiResponse(
        data=PaginatedResponse.create(
            items=[MpesaC2BEventResponse.model_validate(e) for e in events],
            total=total,
            page=page,
            limit=limit,
        )
    )


@router.post(
    "/c2b/events/{event_id}/link",
    response_model=ApiResponse[PaymentResponse],
)
async def link_unmatched_mpesa_event(
    event_id: int,
    payload: MpesaLinkEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    mpesa_service = MpesaC2BService(db)
    event = await mpesa_service.link_event_to_student(event_id=event_id, student_id=payload.student_id)

    if event.payment_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Payment not created")

    payment_service = PaymentService(db)
    payment = await payment_service.get_payment_by_id(event.payment_id)
    return ApiResponse(data=PaymentResponse.model_validate(payment), message="Event linked to payment")


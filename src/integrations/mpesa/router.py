from __future__ import annotations
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.config import settings
from src.core.database.session import get_db
from src.core.school_settings.service import get_school_settings
from src.integrations.mpesa.schemas import (
    MpesaC2BConfirmationPayload,
    MpesaC2BResponse,
    MpesaC2BEventResponse,
    MpesaC2BValidationPayload,
    MpesaLinkEventRequest,
    MpesaSandboxTopUpRequest,
    MpesaSandboxTopUpResponse,
)
from src.integrations.mpesa.service import MpesaC2BService
from src.integrations.mpesa.utils import format_student_number_short
from src.modules.payments.schemas import PaymentResponse
from src.modules.payments.service import PaymentService
from src.modules.students.models import Student
from src.shared.schemas.base import ApiResponse, PaginatedResponse


# Public C2B webhooks must not include "mpesa" in the path
# (per Daraja docs/UI examples).
# Keep internal/admin endpoints under /mpesa/*.
router = APIRouter(tags=["M-Pesa"])


@router.post("/c2b/validation/{token}", response_model=MpesaC2BResponse)
async def mpesa_c2b_validation(
    token: str,
    payload: MpesaC2BValidationPayload,
    db: AsyncSession = Depends(get_db),
):
    service = MpesaC2BService(db)
    if not service.verify_webhook_token(token):
        # Avoid exposing endpoint existence when token isn't configured/mismatched.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    ok = await service.validate_bill_ref(payload)
    # MVP default: accept even if unmatched; confirmation will persist unmatched
    # for manual handling.
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    await service.process_confirmation(payload)
    return MpesaC2BResponse(ResultCode=0, ResultDesc="Accepted")


@router.get(
    "/mpesa/c2b/events/unmatched",
    response_model=ApiResponse[PaginatedResponse[MpesaC2BEventResponse]],
)
async def list_unmatched_mpesa_events(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
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
    "/mpesa/c2b/events/{event_id}/link",
    response_model=ApiResponse[PaymentResponse],
)
async def link_unmatched_mpesa_event(
    event_id: int,
    payload: MpesaLinkEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    mpesa_service = MpesaC2BService(db)
    event = await mpesa_service.link_event_to_student(
        event_id=event_id,
        student_id=payload.student_id,
    )

    if event.payment_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment not created",
        )

    payment_service = PaymentService(db)
    payment = await payment_service.get_payment_by_id(event.payment_id)
    return ApiResponse(
        data=PaymentResponse.model_validate(payment),
        message="Event linked to payment",
    )


@router.post(
    "/mpesa/c2b/sandbox/topup",
    response_model=ApiResponse[MpesaSandboxTopUpResponse],
)
async def sandbox_mpesa_topup(
    payload: MpesaSandboxTopUpRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    """
    Dev/sandbox-only endpoint to simulate an M-Pesa C2B confirmation callback.

    Disabled in production.
    """
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    bill_ref = (payload.bill_ref_number or "").strip() or None

    if payload.student_id is not None:
        # Derive BillRefNumber in the same format as UI (short Admission#)
        # when possible.
        student = await db.scalar(
            select(Student).where(Student.id == payload.student_id)
        )
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")
        bill_ref = (
            format_student_number_short(student.student_number)
            or student.student_number
        )

    school_settings = await get_school_settings(db)
    shortcode = (school_settings.mpesa_business_number or "").strip() or None

    trans_id = payload.trans_id or f"SIM-{uuid4().hex[:16]}"

    confirmation = MpesaC2BConfirmationPayload(
        TransID=trans_id,
        TransTime=payload.trans_time,
        TransAmount=payload.amount,
        BusinessShortCode=shortcode,
        BillRefNumber=bill_ref,
        MSISDN=payload.msisdn,
        FirstName=payload.first_name,
        LastName=payload.last_name,
    )

    mpesa_service = MpesaC2BService(db)
    event = await mpesa_service.process_confirmation(confirmation)

    payment = None
    if event.payment_id is not None:
        payment_service = PaymentService(db)
        payment_obj = await payment_service.get_payment_by_id(event.payment_id)
        payment = PaymentResponse.model_validate(payment_obj)

    return ApiResponse(
        data=MpesaSandboxTopUpResponse(
            event=MpesaC2BEventResponse.model_validate(event),
            payment=payment,
        ),
        message="Simulated M-Pesa top-up processed",
    )

"""API endpoints for Reservations module."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.reservations.models import ReservationStatus
from src.modules.reservations.schemas import (
    ReservationCancelRequest,
    ReservationConfigureComponentsRequest,
    ReservationIssueRequest,
    ReservationItemResponse,
    ReservationResponse,
)
from src.modules.reservations.service import ReservationService
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/reservations", tags=["Reservations"])


def _map_reservation(reservation) -> ReservationResponse:
    student_name = None
    if getattr(reservation, "student", None) is not None:
        student_name = reservation.student.full_name
    return ReservationResponse(
        id=reservation.id,
        student_id=reservation.student_id,
        student_name=student_name,
        invoice_id=reservation.invoice_id,
        invoice_line_id=reservation.invoice_line_id,
        status=ReservationStatus(reservation.status),
        created_by_id=reservation.created_by_id,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        items=[
            ReservationItemResponse(
                id=item.id,
                item_id=item.item_id,
                item_sku=item.item.sku_code if item.item else None,
                item_name=item.item.name if item.item else None,
                quantity_required=item.quantity_required,
                quantity_issued=item.quantity_issued,
            )
            for item in reservation.items
        ],
    )


@router.get("", response_model=ApiResponse[PaginatedResponse[ReservationResponse]])
async def list_reservations(
    student_id: int | None = Query(None),
    invoice_id: int | None = Query(None),
    status: ReservationStatus | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT
        )
    ),
):
    service = ReservationService(db)
    reservations, total = await service.list_reservations(
        student_id=student_id,
        invoice_id=invoice_id,
        status=status,
        page=page,
        limit=limit,
    )
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_map_reservation(r) for r in reservations],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get("/{reservation_id}", response_model=ApiResponse[ReservationResponse])
async def get_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.USER, UserRole.ACCOUNTANT
        )
    ),
):
    service = ReservationService(db)
    reservation = await service.get_by_id(reservation_id)
    return ApiResponse(success=True, data=_map_reservation(reservation))


@router.post(
    "/{reservation_id}/issue",
    response_model=ApiResponse[ReservationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def issue_reservation_items(
    reservation_id: int,
    payload: ReservationIssueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    service = ReservationService(db)
    await service.issue_items(
        reservation_id=reservation_id,
        items=[(i.reservation_item_id, i.quantity) for i in payload.items],
        issued_by_id=current_user.id,
        notes=payload.notes,
    )
    reservation = await service.get_by_id(reservation_id)
    return ApiResponse(success=True, data=_map_reservation(reservation))


@router.post(
    "/{reservation_id}/cancel",
    response_model=ApiResponse[ReservationResponse],
)
async def cancel_reservation(
    reservation_id: int,
    payload: ReservationCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
):
    service = ReservationService(db)
    reservation = await service.cancel_reservation(
        reservation_id=reservation_id,
        cancelled_by_id=current_user.id,
        reason=payload.reason,
        commit=True,
    )
    return ApiResponse(success=True, data=_map_reservation(reservation))


@router.post(
    "/{reservation_id}/components",
    response_model=ApiResponse[ReservationResponse],
)
async def configure_reservation_components(
    reservation_id: int,
    payload: ReservationConfigureComponentsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    """Configure concrete components for an editable-kit reservation.

    Allowed only before any items are issued.
    """
    service = ReservationService(db)
    reservation = await service.configure_components(
        reservation_id=reservation_id,
        components=payload.components,
        configured_by_id=current_user.id,
    )
    return ApiResponse(success=True, data=_map_reservation(reservation))

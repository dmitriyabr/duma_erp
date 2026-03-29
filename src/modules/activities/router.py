"""API endpoints for paid activities."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.activities.models import ActivityParticipantStatus, ActivityStatus
from src.modules.activities.schemas import (
    ActivityCreate,
    ActivityInvoiceGenerationResult,
    ActivityListFilters,
    ActivityParticipantAddRequest,
    ActivityParticipantExcludeRequest,
    ActivityParticipantResponse,
    ActivityResponse,
    ActivitySummaryResponse,
    ActivityUpdate,
)
from src.modules.activities.service import ActivityService
from src.shared.schemas.base import ApiResponse, PaginatedResponse
from src.shared.utils.money import round_money

router = APIRouter(prefix="/activities", tags=["Activities"])

ReadRoles = (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
ManageRoles = (UserRole.SUPER_ADMIN, UserRole.ADMIN)


def _participant_to_response(participant) -> ActivityParticipantResponse:
    student = participant.student
    invoice = participant.invoice
    return ActivityParticipantResponse(
        id=participant.id,
        student_id=student.id,
        student_name=student.full_name,
        student_number=student.student_number,
        grade_id=student.grade_id,
        grade_name=student.grade.name if student.grade else None,
        status=participant.status,
        selected_amount=participant.selected_amount,
        invoice_id=participant.invoice_id,
        invoice_number=invoice.invoice_number if invoice else None,
        invoice_status=invoice.status if invoice else None,
        invoice_total=invoice.total if invoice else None,
        invoice_amount_due=invoice.amount_due if invoice else None,
        added_manually=participant.added_manually,
        excluded_reason=participant.excluded_reason,
        created_at=participant.created_at,
        updated_at=participant.updated_at,
    )


def _activity_metrics(activity) -> dict[str, Decimal | int]:
    participants_total = len(activity.participants)
    planned_count = 0
    invoiced_count = 0
    paid_count = 0
    cancelled_count = 0
    skipped_count = 0
    total_invoiced_amount = Decimal("0.00")
    total_outstanding_amount = Decimal("0.00")

    for participant in activity.participants:
        if participant.status == ActivityParticipantStatus.PLANNED.value:
            planned_count += 1
        elif participant.status == ActivityParticipantStatus.INVOICED.value:
            invoiced_count += 1
        elif participant.status == ActivityParticipantStatus.CANCELLED.value:
            cancelled_count += 1
        elif participant.status == ActivityParticipantStatus.SKIPPED.value:
            skipped_count += 1

        invoice = participant.invoice
        if not invoice:
            continue
        if invoice.status not in ("cancelled", "void"):
            total_invoiced_amount += invoice.total
            total_outstanding_amount += invoice.amount_due
        if (
            participant.status != ActivityParticipantStatus.CANCELLED.value
            and invoice.status == "paid"
        ):
            paid_count += 1

    return {
        "participants_total": participants_total,
        "planned_count": planned_count,
        "invoiced_count": invoiced_count,
        "paid_count": paid_count,
        "cancelled_count": cancelled_count,
        "skipped_count": skipped_count,
        "total_invoiced_amount": round_money(total_invoiced_amount),
        "total_outstanding_amount": round_money(total_outstanding_amount),
    }


def _activity_to_summary(activity) -> ActivitySummaryResponse:
    metrics = _activity_metrics(activity)
    return ActivitySummaryResponse(
        id=activity.id,
        activity_number=activity.activity_number,
        code=activity.code,
        name=activity.name,
        activity_date=activity.activity_date,
        due_date=activity.due_date,
        term_id=activity.term_id,
        term_name=activity.term.display_name if activity.term else None,
        status=activity.status,
        audience_type=activity.audience_type,
        amount=activity.amount,
        requires_full_payment=activity.requires_full_payment,
        participants_total=int(metrics["participants_total"]),
        planned_count=int(metrics["planned_count"]),
        invoiced_count=int(metrics["invoiced_count"]),
        paid_count=int(metrics["paid_count"]),
        cancelled_count=int(metrics["cancelled_count"]),
        skipped_count=int(metrics["skipped_count"]),
        total_invoiced_amount=metrics["total_invoiced_amount"],
        total_outstanding_amount=metrics["total_outstanding_amount"],
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


def _activity_to_response(activity) -> ActivityResponse:
    summary = _activity_to_summary(activity)
    participants = sorted(
        activity.participants,
        key=lambda participant: (
            participant.student.first_name.lower(),
            participant.student.last_name.lower(),
            participant.student.id,
        ),
    )
    audience_student_ids = [
        participant.student_id
        for participant in participants
        if participant.status
        not in (
            ActivityParticipantStatus.CANCELLED.value,
            ActivityParticipantStatus.SKIPPED.value,
        )
    ]
    return ActivityResponse(
        **summary.model_dump(),
        description=activity.description,
        notes=activity.notes,
        created_activity_kit_id=activity.created_activity_kit_id,
        created_by_id=activity.created_by_id,
        audience_grade_ids=[scope.grade_id for scope in activity.grade_scopes],
        audience_student_ids=audience_student_ids,
        participants=[_participant_to_response(participant) for participant in participants],
    )


@router.post("", response_model=ApiResponse[ActivityResponse], status_code=status.HTTP_201_CREATED)
async def create_activity(
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ManageRoles)),
):
    """Create a paid activity."""
    service = ActivityService(db)
    activity = await service.create_activity(data, current_user.id)
    return ApiResponse(
        success=True,
        message="Activity created successfully",
        data=_activity_to_response(activity),
    )


@router.get("", response_model=ApiResponse[PaginatedResponse[ActivitySummaryResponse]])
async def list_activities(
    status: ActivityStatus | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ReadRoles)),
):
    """List paid activities."""
    service = ActivityService(db)
    filters = ActivityListFilters(status=status, search=search, page=page, limit=limit)
    activities, total = await service.list_activities(filters)
    return ApiResponse(
        success=True,
        data=PaginatedResponse.create(
            items=[_activity_to_summary(activity) for activity in activities],
            total=total,
            page=page,
            limit=limit,
        ),
    )


@router.get("/{activity_id}", response_model=ApiResponse[ActivityResponse])
async def get_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ReadRoles)),
):
    """Get one paid activity with audience and billing details."""
    service = ActivityService(db)
    activity = await service.get_activity_by_id(activity_id)
    return ApiResponse(success=True, data=_activity_to_response(activity))


@router.patch("/{activity_id}", response_model=ApiResponse[ActivityResponse])
async def update_activity(
    activity_id: int,
    data: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ManageRoles)),
):
    """Update a paid activity."""
    service = ActivityService(db)
    activity = await service.update_activity(activity_id, data, current_user.id)
    return ApiResponse(
        success=True,
        message="Activity updated successfully",
        data=_activity_to_response(activity),
    )


@router.post(
    "/{activity_id}/participants",
    response_model=ApiResponse[ActivityResponse],
)
async def add_activity_participant(
    activity_id: int,
    data: ActivityParticipantAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ManageRoles)),
):
    """Add one student to the activity audience."""
    service = ActivityService(db)
    activity = await service.add_participant(activity_id, data, current_user.id)
    return ApiResponse(
        success=True,
        message="Participant added successfully",
        data=_activity_to_response(activity),
    )


@router.post(
    "/{activity_id}/participants/{participant_id}/exclude",
    response_model=ApiResponse[ActivityResponse],
)
async def exclude_activity_participant(
    activity_id: int,
    participant_id: int,
    data: ActivityParticipantExcludeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ManageRoles)),
):
    """Exclude a participant and cancel unpaid invoice if linked."""
    service = ActivityService(db)
    activity = await service.exclude_participant(
        activity_id,
        participant_id,
        current_user.id,
        data.reason,
    )
    return ApiResponse(
        success=True,
        message="Participant excluded successfully",
        data=_activity_to_response(activity),
    )


@router.post(
    "/{activity_id}/generate-invoices",
    response_model=ApiResponse[ActivityInvoiceGenerationResult],
)
async def generate_activity_invoices(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*ManageRoles)),
):
    """Generate missing activity invoices for planned participants."""
    service = ActivityService(db)
    result = await service.generate_invoices(activity_id, current_user.id)
    return ApiResponse(
        success=True,
        message="Activity invoices generated successfully",
        data=result,
    )

"""API endpoints for Accountant: audit trail and exports (read-only)."""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit.service import list_audit_entries
from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.accountant.schemas import AuditTrailEntryResponse
from src.modules.accountant.service import (
    build_student_payments_csv,
    list_student_payments_for_export,
)
from src.shared.schemas.base import ApiResponse, PaginatedResponse

router = APIRouter(prefix="/accountant", tags=["Accountant"])

# Allow Accountant and Admins to access accountant endpoints
AccountantOrAdmin = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT))


@router.get(
    "/audit-trail",
    response_model=ApiResponse[PaginatedResponse[AuditTrailEntryResponse]],
)
async def get_audit_trail(
    date_from: date | None = Query(None, description="Filter from date (inclusive)"),
    date_to: date | None = Query(None, description="Filter to date (inclusive)"),
    user_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = AccountantOrAdmin,
):
    """List audit log entries with filters (for Accountant / Admin)."""
    from datetime import timezone
    dt_from = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc) if date_from else None
    dt_to = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc) if date_to else None
    entries, total = await list_audit_entries(
        db,
        date_from=dt_from,
        date_to=dt_to,
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        page=page,
        limit=limit,
    )
    items = [
        AuditTrailEntryResponse(
            id=a.id,
            user_id=a.user_id,
            user_full_name=user_full_name,
            action=a.action,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            entity_identifier=a.entity_identifier,
            old_values=a.old_values,
            new_values=a.new_values,
            comment=a.comment,
            created_at=a.created_at,
        )
        for a, user_full_name in entries
    ]
    return ApiResponse(
        data=PaginatedResponse.create(items=items, total=total, page=page, limit=limit),
    )


@router.get("/export/student-payments")
async def export_student_payments(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    format: str = Query("csv", description="Format: csv"),
    db: AsyncSession = Depends(get_db),
    current_user: User = AccountantOrAdmin,
):
    """Export student payments (receipts) for date range as CSV."""
    if format.lower() != "csv":
        return Response(
            content="Only CSV format is supported",
            status_code=400,
        )
    rows = await list_student_payments_for_export(
        db,
        date_from=start_date,
        date_to=end_date,
    )
    content = build_student_payments_csv(rows)
    filename = f"student_payments_{start_date}_{end_date}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

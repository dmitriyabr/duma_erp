"""Schemas for paid activities."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from src.modules.activities.models import (
    ActivityAudienceType,
    ActivityParticipantStatus,
    ActivityStatus,
)
from src.shared.schemas.base import BaseSchema


class ActivityCreate(BaseSchema):
    """Create a paid activity and snapshot its audience."""

    code: str | None = Field(None, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    activity_date: date | None = None
    due_date: date | None = None
    term_id: int | None = None
    amount: Decimal = Field(..., gt=0)
    requires_full_payment: bool = False
    notes: str | None = None
    status: ActivityStatus = ActivityStatus.DRAFT
    audience_type: ActivityAudienceType
    grade_ids: list[int] = Field(default_factory=list)
    student_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_audience(self):
        if self.audience_type == ActivityAudienceType.ALL_ACTIVE:
            if self.grade_ids or self.student_ids:
                raise ValueError("all_active activities cannot include grade_ids or student_ids")
        elif self.audience_type == ActivityAudienceType.GRADES:
            if not self.grade_ids:
                raise ValueError("grades audience requires at least one grade_id")
            if self.student_ids:
                raise ValueError("grades audience cannot include student_ids")
        elif self.audience_type == ActivityAudienceType.MANUAL:
            if not self.student_ids:
                raise ValueError("manual audience requires at least one student_id")
            if self.grade_ids:
                raise ValueError("manual audience cannot include grade_ids")
        return self


class ActivityUpdate(BaseSchema):
    """Partial update for an activity."""

    code: str | None = Field(None, max_length=100)
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    activity_date: date | None = None
    due_date: date | None = None
    term_id: int | None = None
    amount: Decimal | None = Field(None, gt=0)
    requires_full_payment: bool | None = None
    notes: str | None = None
    status: ActivityStatus | None = None
    audience_type: ActivityAudienceType | None = None
    grade_ids: list[int] | None = None
    student_ids: list[int] | None = None


class ActivityParticipantAddRequest(BaseSchema):
    """Add a manual participant to an activity."""

    student_id: int
    selected_amount: Decimal | None = Field(None, gt=0)


class ActivityParticipantExcludeRequest(BaseSchema):
    """Exclude a participant from an activity."""

    reason: str | None = Field(None, max_length=500)


class ActivityListFilters(BaseSchema):
    """Filters for listing activities."""

    status: ActivityStatus | None = None
    search: str | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=200)


class ActivityParticipantResponse(BaseSchema):
    """Activity participant with billing context."""

    id: int
    student_id: int
    student_name: str
    student_number: str
    grade_id: int
    grade_name: str | None = None
    status: str
    selected_amount: Decimal
    invoice_id: int | None = None
    invoice_number: str | None = None
    invoice_status: str | None = None
    invoice_total: Decimal | None = None
    invoice_amount_due: Decimal | None = None
    added_manually: bool
    excluded_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ActivitySummaryResponse(BaseSchema):
    """List view for one activity."""

    id: int
    activity_number: str
    code: str | None = None
    name: str
    activity_date: date | None = None
    due_date: date | None = None
    term_id: int | None = None
    term_name: str | None = None
    status: str
    audience_type: str
    amount: Decimal
    requires_full_payment: bool
    participants_total: int
    planned_count: int
    invoiced_count: int
    paid_count: int
    cancelled_count: int
    skipped_count: int
    total_invoiced_amount: Decimal
    total_outstanding_amount: Decimal
    created_at: datetime
    updated_at: datetime


class ActivityResponse(ActivitySummaryResponse):
    """Full activity details."""

    description: str | None = None
    notes: str | None = None
    created_activity_kit_id: int | None = None
    created_by_id: int
    audience_grade_ids: list[int] = Field(default_factory=list)
    audience_student_ids: list[int] = Field(default_factory=list)
    participants: list[ActivityParticipantResponse] = Field(default_factory=list)


class ActivityInvoiceGenerationResult(BaseSchema):
    """Result of batch invoice generation for one activity."""

    activity_id: int
    invoices_created: int
    participants_skipped: int
    affected_student_ids: list[int] = Field(default_factory=list)

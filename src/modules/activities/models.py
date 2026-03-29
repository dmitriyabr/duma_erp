"""Models for paid student activities."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import BaseModel


class ActivityStatus(StrEnum):
    """High-level activity lifecycle."""

    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ActivityAudienceType(StrEnum):
    """How the audience is selected."""

    ALL_ACTIVE = "all_active"
    GRADES = "grades"
    MANUAL = "manual"


class ActivityParticipantStatus(StrEnum):
    """Billing state for one participant."""

    PLANNED = "planned"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class Activity(BaseModel):
    """Paid activity that can be billed to many students."""

    __tablename__ = "activities"

    activity_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    code: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("terms.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActivityStatus.DRAFT.value, index=True
    )
    audience_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    requires_full_payment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_activity_kit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("kits.id"), nullable=True
    )
    created_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )

    term: Mapped["Term | None"] = relationship("Term")
    created_activity_kit: Mapped["Kit | None"] = relationship("Kit")
    created_by: Mapped["User"] = relationship("User")
    grade_scopes: Mapped[list["ActivityGradeScope"]] = relationship(
        "ActivityGradeScope",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityGradeScope.id",
    )
    participants: Mapped[list["ActivityParticipant"]] = relationship(
        "ActivityParticipant",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityParticipant.id",
    )


class ActivityGradeScope(BaseModel):
    """Selected grades for grade-based activity audience."""

    __tablename__ = "activity_grade_scopes"
    __table_args__ = (
        UniqueConstraint("activity_id", "grade_id", name="uq_activity_grade_scope"),
    )

    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grades.id"), nullable=False, index=True
    )

    activity: Mapped["Activity"] = relationship("Activity", back_populates="grade_scopes")
    grade: Mapped["Grade"] = relationship("Grade")


class ActivityParticipant(BaseModel):
    """One student in an activity audience snapshot."""

    __tablename__ = "activity_participants"
    __table_args__ = (
        UniqueConstraint("activity_id", "student_id", name="uq_activity_participant"),
    )

    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActivityParticipantStatus.PLANNED.value, index=True
    )
    selected_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("invoices.id"), nullable=True, index=True
    )
    invoice_line_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("invoice_lines.id"), nullable=True
    )
    excluded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_manually: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    activity: Mapped["Activity"] = relationship("Activity", back_populates="participants")
    student: Mapped["Student"] = relationship("Student")
    invoice: Mapped["Invoice | None"] = relationship("Invoice", foreign_keys=[invoice_id])
    invoice_line: Mapped["InvoiceLine | None"] = relationship(
        "InvoiceLine", foreign_keys=[invoice_line_id]
    )


# Imported at end for SQLAlchemy relationship resolution.
from src.core.auth.models import User
from src.modules.invoices.models import Invoice, InvoiceLine
from src.modules.items.models import Kit
from src.modules.students.models import Grade, Student
from src.modules.terms.models import Term

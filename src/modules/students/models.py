"""Student and Grade models."""

from datetime import date
from enum import StrEnum

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class Gender(StrEnum):
    """Gender enumeration."""

    MALE = "male"
    FEMALE = "female"


class StudentStatus(StrEnum):
    """Student status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Grade(Base):
    """School grade/class level.

    Examples: Play Group, PP1, PP2, Grade 1-6
    """

    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True
    )  # e.g., "PG", "PP1", "G1"
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "Play Group", "Pre-Primary 1", "Grade 1"
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # For sorting
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    students: Mapped[list["Student"]] = relationship("Student", back_populates="grade")


class Student(Base):
    """Student enrolled in the school."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    student_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )  # STU-YYYY-NNNNNN

    # Personal info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)  # male | female

    # Academic info
    grade_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grades.id"), nullable=False, index=True
    )
    transport_zone_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transport_zones.id"), nullable=True, index=True
    )

    # Guardian info
    guardian_name: Mapped[str] = mapped_column(String(200), nullable=False)
    guardian_phone: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # Kenyan format +254...
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StudentStatus.ACTIVE.value, index=True
    )
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Cached credit balance (updated when payments/allocations change)
    cached_credit_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )

    # Other
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    grade: Mapped["Grade"] = relationship("Grade", back_populates="students")
    transport_zone: Mapped["TransportZone | None"] = relationship("TransportZone")
    created_by: Mapped["User"] = relationship("User")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="student")

    @property
    def full_name(self) -> str:
        """Full name of the student."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        """Check if student is active."""
        return self.status == StudentStatus.ACTIVE.value


# Import at the end to avoid circular imports
from src.modules.terms.models import TransportZone
from src.core.auth.models import User

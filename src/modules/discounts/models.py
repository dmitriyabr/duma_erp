"""Discount models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class DiscountValueType(StrEnum):
    """Discount value type."""

    FIXED = "fixed"
    PERCENTAGE = "percentage"


class StudentDiscountAppliesTo(StrEnum):
    """What student discount applies to."""

    SCHOOL_FEE = "school_fee"
    # Can expand: TRANSPORT = "transport", ALL = "all"


class DiscountReason(Base):
    """Reference table for discount reasons."""

    __tablename__ = "discount_reasons"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Discount(Base):
    """Applied discount on an invoice line."""

    __tablename__ = "discounts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoice_lines.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Discount value
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # fixed | percentage
    value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Amount or percentage
    calculated_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Actual amount deducted

    # Reason
    reason_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("discount_reasons.id"), nullable=True
    )
    reason_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Custom reason or additional details

    # Auto-applied from StudentDiscount
    student_discount_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("student_discounts.id"), nullable=True
    )

    # Metadata
    applied_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    invoice_line: Mapped["InvoiceLine"] = relationship("InvoiceLine")
    reason: Mapped["DiscountReason | None"] = relationship("DiscountReason")
    student_discount: Mapped["StudentDiscount | None"] = relationship("StudentDiscount")
    applied_by: Mapped["User"] = relationship("User")


class StudentDiscount(Base):
    """Standing discount for a student (applied to future invoices)."""

    __tablename__ = "student_discounts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.id"), nullable=False, index=True
    )

    # What it applies to
    applies_to: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StudentDiscountAppliesTo.SCHOOL_FEE.value
    )

    # Discount value
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # fixed | percentage
    value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Amount or percentage

    # Reason
    reason_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("discount_reasons.id"), nullable=True
    )
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Metadata
    created_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student")
    reason: Mapped["DiscountReason | None"] = relationship("DiscountReason")
    created_by: Mapped["User"] = relationship("User")


# Import at the end to avoid circular imports
from src.modules.invoices.models import InvoiceLine
from src.modules.students.models import Student
from src.core.auth.models import User

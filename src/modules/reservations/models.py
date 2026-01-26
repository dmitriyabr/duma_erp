"""Reservation models for paid invoice items."""

from enum import StrEnum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class ReservationStatus(StrEnum):
    """Reservation status enumeration."""

    PENDING = "pending"
    PARTIAL = "partial"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class Reservation(Base):
    """Reservation created after invoice line is fully paid."""

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.id"), nullable=False, index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoices.id"), nullable=False, index=True
    )
    invoice_line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoice_lines.id"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReservationStatus.PENDING.value, index=True
    )
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
    invoice: Mapped["Invoice"] = relationship("Invoice")
    invoice_line: Mapped["InvoiceLine"] = relationship(
        "InvoiceLine", back_populates="reservation"
    )
    created_by: Mapped["User"] = relationship("User")
    items: Mapped[list["ReservationItem"]] = relationship(
        "ReservationItem", back_populates="reservation", cascade="all, delete-orphan"
    )


class ReservationItem(Base):
    """Reserved item with required/reserved/issued quantities."""

    __tablename__ = "reservation_items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )
    quantity_required: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_issued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="items")
    item: Mapped["Item"] = relationship("Item")

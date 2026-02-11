"""Inventory models for stock management."""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class MovementType(StrEnum):
    """Stock movement type enumeration."""

    RECEIPT = "receipt"  # Incoming stock (purchase, return from customer, etc.)
    ISSUE = "issue"  # Outgoing stock (sale, issuance to student/employee)
    RESERVE = "reserve"  # Reserve stock for pending issuance
    UNRESERVE = "unreserve"  # Cancel reservation
    ADJUSTMENT = "adjustment"  # Inventory adjustment (correction, write-off)


class IssuanceType(StrEnum):
    """Issuance type enumeration."""

    INTERNAL = "internal"  # Internal issuance (to employee, kitchen, etc.)
    RESERVATION = "reservation"  # Issuance from reservation (student invoice)


class RecipientType(StrEnum):
    """Recipient type enumeration."""

    EMPLOYEE = "employee"  # User (employee)
    DEPARTMENT = "department"  # Department (kitchen, etc.) — legacy, use OTHER with name
    STUDENT = "student"  # Student (reservation or manual issuance)
    OTHER = "other"  # Free-text recipient (recipient_id not used)


class IssuanceStatus(StrEnum):
    """Issuance status enumeration."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Stock(Base):
    """Current stock levels for items.

    Only items with item_type='product' should have stock records.
    """

    __tablename__ = "stock"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, unique=True, index=True
    )
    quantity_on_hand: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # Physical quantity in warehouse
    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )  # Weighted average cost
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="stock")
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="stock", order_by="desc(StockMovement.created_at)"
    )

    @property
    def quantity_available(self) -> int:
        """Quantity available on hand.

        Note: reservations are demand-based (no physical allocation), so availability
        for issuing is determined by quantity_on_hand only. UI/API may compute "free"
        as on_hand - owed.
        """
        return self.quantity_on_hand


class StockMovement(Base):
    """History of all stock movements."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )  # Denormalized for easier queries
    movement_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # receipt, issue, reserve, unreserve, adjustment
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Positive for in, negative for out
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )  # Cost per unit (for receipt movements)
    quantity_before: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Stock quantity before movement
    quantity_after: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Stock quantity after movement
    average_cost_before: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Average cost before movement
    average_cost_after: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Average cost after movement
    reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g., "purchase_order", "invoice", "adjustment"
    reference_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )  # ID of the reference document
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="movements")
    item: Mapped["Item"] = relationship("Item")
    created_by: Mapped["User"] = relationship("User")


class Issuance(Base):
    """Unified issuance record for both internal and reservation-based issuances.

    Internal: issuance to employees, departments (kitchen, etc.)
    Reservation: issuance to students based on paid invoices
    """

    __tablename__ = "issuances"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    issuance_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    issuance_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # internal | reservation
    recipient_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # employee | department | student | other
    recipient_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )  # user_id for employee, student_id for student; null for other
    recipient_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # Denormalized for display
    reservation_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )  # Link to Reservation (for type=reservation)
    issued_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    issued_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IssuanceStatus.COMPLETED.value
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    issued_by: Mapped["User"] = relationship("User")
    items: Mapped[list["IssuanceItem"]] = relationship(
        "IssuanceItem", back_populates="issuance", cascade="all, delete-orphan"
    )


class IssuanceItem(Base):
    """Item included in an issuance."""

    __tablename__ = "issuance_items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    issuance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("issuances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Cost at time of issuance (from Stock.average_cost)
    reservation_item_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )  # Link to ReservationItem (for reservation issuances)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    issuance: Mapped["Issuance"] = relationship("Issuance", back_populates="items")
    item: Mapped["Item"] = relationship("Item")


# Import at the end to avoid circular imports
from src.modules.items.models import Item
from src.core.auth.models import User

"""Procurement models (Purchase Orders)."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

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


class PurchaseOrderStatus(StrEnum):
    """Purchase order status enumeration."""

    DRAFT = "draft"
    ORDERED = "ordered"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class PurchaseOrder(Base):
    """Purchase order for supplier procurement."""

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )

    supplier_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    supplier_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purpose_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_purposes.id"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=PurchaseOrderStatus.DRAFT.value, index=True
    )

    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    track_to_warehouse: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    expected_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    received_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    paid_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    debt_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    created_by: Mapped["User"] = relationship("User")
    purpose: Mapped["PaymentPurpose"] = relationship("PaymentPurpose")


class PurchaseOrderLine(Base):
    """Purchase order line item."""

    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id"), nullable=False, index=True
    )

    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    quantity_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_cancelled: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    line_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="lines"
    )
    item: Mapped["Item"] = relationship("Item")


class GoodsReceivedStatus(StrEnum):
    """Goods received note status."""

    DRAFT = "draft"
    APPROVED = "approved"
    CANCELLED = "cancelled"


class GoodsReceivedNote(Base):
    """Goods received note (GRN)."""

    __tablename__ = "goods_received_notes"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    grn_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GoodsReceivedStatus.DRAFT.value, index=True
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder")
    lines: Mapped[list["GoodsReceivedLine"]] = relationship(
        "GoodsReceivedLine", back_populates="grn", cascade="all, delete-orphan"
    )
    received_by: Mapped["User"] = relationship("User", foreign_keys=[received_by_id])
    approved_by: Mapped["User"] = relationship("User", foreign_keys=[approved_by_id])


class GoodsReceivedLine(Base):
    """Goods received line."""

    __tablename__ = "goods_received_lines"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    grn_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("goods_received_notes.id"), nullable=False, index=True
    )
    po_line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order_lines.id"), nullable=False
    )
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True
    )
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    grn: Mapped["GoodsReceivedNote"] = relationship(
        "GoodsReceivedNote", back_populates="lines"
    )
    po_line: Mapped["PurchaseOrderLine"] = relationship("PurchaseOrderLine")
    item: Mapped["Item"] = relationship("Item")


class PaymentPurpose(Base):
    """Payment purpose/category."""

    __tablename__ = "payment_purposes"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    purpose_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="expense", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ProcurementPaymentStatus(StrEnum):
    """Procurement payment status."""

    POSTED = "posted"
    CANCELLED = "cancelled"


class ProcurementPaymentMethod(StrEnum):
    """Procurement payment method."""

    EMPLOYEE = "employee"
    MPESA = "mpesa"
    BANK = "bank"
    CASH = "cash"
    OTHER = "other"


class ProcurementPayment(Base):
    """Payment related to a purchase order (or standalone)."""

    __tablename__ = "procurement_payments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    payment_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )

    po_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id"), nullable=True, index=True
    )
    purpose_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment_purposes.id"), nullable=False
    )
    payee_name: Mapped[str | None] = mapped_column(String(300), nullable=True)

    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_attachment_id: Mapped[int | None] = mapped_column(BigIntPK, nullable=True)

    company_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    employee_paid_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProcurementPaymentStatus.POSTED.value,
        index=True,
    )

    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder")
    purpose: Mapped["PaymentPurpose"] = relationship("PaymentPurpose")
    employee_paid: Mapped["User"] = relationship("User", foreign_keys=[employee_paid_id])
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    cancelled_by: Mapped["User"] = relationship("User", foreign_keys=[cancelled_by_id])

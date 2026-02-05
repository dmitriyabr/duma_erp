"""Invoice and InvoiceLine models."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class InvoiceType(StrEnum):
    """Invoice type enumeration."""

    SCHOOL_FEE = "school_fee"
    TRANSPORT = "transport"
    ADHOC = "adhoc"


class InvoiceStatus(StrEnum):
    """Invoice status enumeration."""

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    VOID = "void"


class Invoice(Base):
    """Invoice for a student."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )

    # Relations
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.id"), nullable=False, index=True
    )
    term_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("terms.id"), nullable=True, index=True
    )

    # Type and status
    invoice_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # school_fee | transport | adhoc
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InvoiceStatus.DRAFT.value, index=True
    )

    # Dates
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Amounts (Decimal with 2 decimal places)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    paid_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    amount_due: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    term: Mapped["Term | None"] = relationship("Term")
    created_by: Mapped["User"] = relationship("User")
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan"
    )
    allocations: Mapped[list["CreditAllocation"]] = relationship(
        "CreditAllocation", back_populates="invoice"
    )

    @property
    def is_editable(self) -> bool:
        """Check if invoice can be edited (add/remove lines)."""
        return self.status == InvoiceStatus.DRAFT.value

    @property
    def can_receive_payment(self) -> bool:
        """Check if invoice can receive payments."""
        return self.status in (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
        )

    @property
    def can_be_cancelled(self) -> bool:
        """Check if invoice can be cancelled (no payments received)."""
        return self.status in (
            InvoiceStatus.DRAFT.value,
            InvoiceStatus.ISSUED.value,
        ) and self.paid_total == Decimal("0.00")

    @property
    def can_be_voided(self) -> bool:
        """Check if invoice can be voided (has payments, requires reversal)."""
        return self.status in (
            InvoiceStatus.ISSUED.value,
            InvoiceStatus.PARTIALLY_PAID.value,
        ) and self.paid_total > Decimal("0.00")

    # SKUs that always require full payment (Admission/Interview); used even if kit flag was false
    _REQUIRES_FULL_SKUS = frozenset({"ADMISSION-FEE", "INTERVIEW-FEE"})

    @property
    def requires_full_payment(self) -> bool:
        """
        Check if invoice must be paid in full to be useful.

        Returns True if any line has a kit that requires full payment
        (e.g., products, admission fee), or kit sku is Admission/Interview.

        Note: lines must be loaded for this to work correctly.
        """
        for line in self.lines:
            if not line.kit:
                continue
            if line.kit.sku_code in self._REQUIRES_FULL_SKUS:
                return True
            if line.kit.requires_full_payment:
                return True
        return False


class InvoiceLine(Base):
    """Line item in an invoice."""

    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Kit reference
    kit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kits.id"), nullable=False
    )

    # Line details
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # quantity * unit_price

    # Discount (can be set directly for custom discounts)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )

    # Net and payment tracking
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # line_total - discount_amount
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # net_amount - paid_amount

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")
    kit: Mapped["Kit"] = relationship("Kit")
    reservation: Mapped["Reservation | None"] = relationship(
        "Reservation", uselist=False, back_populates="invoice_line"
    )

    @property
    def is_fully_paid(self) -> bool:
        """Check if line is fully paid."""
        return self.remaining_amount == Decimal("0.00")


class InvoiceLineComponent(Base):
    """Actual inventory item component for an invoice line (for configurable kits)."""

    __tablename__ = "invoice_line_components"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    invoice_line_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("invoice_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("items.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)

    # Relationships
    line: Mapped["InvoiceLine"] = relationship("InvoiceLine", backref="components")


# Import at the end to avoid circular imports
from src.modules.students.models import Student
from src.modules.terms.models import Term
from src.modules.items.models import Kit
from src.core.auth.models import User

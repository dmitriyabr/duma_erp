"""Models for operational budgets and employee advances."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class BudgetStatus(StrEnum):
    """Budget lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class BudgetAdvanceStatus(StrEnum):
    """Budget advance lifecycle status."""

    DRAFT = "draft"
    ISSUED = "issued"
    OVERDUE = "overdue"
    SETTLED = "settled"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class BudgetAdvanceSourceType(StrEnum):
    """How an advance was created."""

    CASH_ISSUE = "cash_issue"
    TRANSFER_IN = "transfer_in"


class BudgetAdvanceTransferType(StrEnum):
    """Business reason for transfer."""

    ROLLOVER = "rollover"
    REASSIGNMENT = "reassignment"
    REALLOCATION = "reallocation"


class BudgetClaimAllocationStatus(StrEnum):
    """Reservation/settlement state for budget claim allocation."""

    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"


class Budget(Base):
    """Operational budget for one purpose and one period."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    budget_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    purpose_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("payment_purposes.id"), nullable=False, index=True)
    period_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_to: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BudgetStatus.DRAFT.value, index=True)
    created_by_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=False)
    approved_by_id: Mapped[int | None] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    purpose: Mapped["PaymentPurpose"] = relationship("PaymentPurpose")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    approved_by: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by_id])
    advances: Mapped[list["BudgetAdvance"]] = relationship(
        "BudgetAdvance", back_populates="budget", cascade="all, delete-orphan"
    )
    claims: Mapped[list["ExpenseClaim"]] = relationship("ExpenseClaim", back_populates="budget")


class BudgetAdvance(Base):
    """Money issued to an employee under a budget."""

    __tablename__ = "budget_advances"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    advance_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    budget_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("budgets.id"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=False, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_issued: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_attachment_id: Mapped[int | None] = mapped_column(BigIntPK, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BudgetAdvanceSourceType.CASH_ISSUE.value
    )
    settlement_due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BudgetAdvanceStatus.DRAFT.value, index=True)
    created_by_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    budget: Mapped["Budget"] = relationship("Budget", back_populates="advances")
    employee: Mapped["User"] = relationship("User", foreign_keys=[employee_id])
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    returns: Mapped[list["BudgetAdvanceReturn"]] = relationship(
        "BudgetAdvanceReturn", back_populates="advance", cascade="all, delete-orphan"
    )
    allocations: Mapped[list["BudgetClaimAllocation"]] = relationship(
        "BudgetClaimAllocation", back_populates="advance", cascade="all, delete-orphan"
    )
    transfer_out_documents: Mapped[list["BudgetAdvanceTransfer"]] = relationship(
        "BudgetAdvanceTransfer",
        foreign_keys="BudgetAdvanceTransfer.from_advance_id",
        back_populates="from_advance",
        cascade="all, delete-orphan",
    )
    transfer_in_document: Mapped["BudgetAdvanceTransfer | None"] = relationship(
        "BudgetAdvanceTransfer",
        foreign_keys="BudgetAdvanceTransfer.created_to_advance_id",
        back_populates="created_to_advance",
        uselist=False,
    )


class BudgetAdvanceReturn(Base):
    """Return of unused money from an advance."""

    __tablename__ = "budget_advance_returns"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    return_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    advance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("budget_advances.id"), nullable=False, index=True)
    return_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    return_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_attachment_id: Mapped[int | None] = mapped_column(BigIntPK, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    advance: Mapped["BudgetAdvance"] = relationship("BudgetAdvance", back_populates="returns")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])


class BudgetAdvanceTransfer(Base):
    """Transfer of remaining balance from one advance into a new advance."""

    __tablename__ = "budget_advance_transfers"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    transfer_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    from_advance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("budget_advances.id"), nullable=False, index=True
    )
    to_budget_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("budgets.id"), nullable=False, index=True)
    to_employee_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=False, index=True)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    transfer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_to_advance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("budget_advances.id"), nullable=False, index=True
    )
    created_by_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    from_advance: Mapped["BudgetAdvance"] = relationship(
        "BudgetAdvance", foreign_keys=[from_advance_id], back_populates="transfer_out_documents"
    )
    to_budget: Mapped["Budget"] = relationship("Budget", foreign_keys=[to_budget_id])
    to_employee: Mapped["User"] = relationship("User", foreign_keys=[to_employee_id])
    created_to_advance: Mapped["BudgetAdvance"] = relationship(
        "BudgetAdvance", foreign_keys=[created_to_advance_id], back_populates="transfer_in_document"
    )
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])


class BudgetClaimAllocation(Base):
    """Allocation of issued budget money to an expense claim."""

    __tablename__ = "budget_claim_allocations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    advance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("budget_advances.id"), nullable=False, index=True)
    claim_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("expense_claims.id"), nullable=False, index=True)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    allocation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BudgetClaimAllocationStatus.RESERVED.value, index=True
    )
    released_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    advance: Mapped["BudgetAdvance"] = relationship("BudgetAdvance", back_populates="allocations")
    claim: Mapped["ExpenseClaim"] = relationship("ExpenseClaim", back_populates="budget_allocations")

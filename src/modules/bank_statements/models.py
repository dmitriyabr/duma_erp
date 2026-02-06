"""Bank statement imports, transactions and reconciliation matches."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base, BigIntPK


class BankStatementImport(Base):
    """One uploaded bank statement file (CSV) with parsed transactions."""

    __tablename__ = "bank_statement_imports"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    attachment_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("attachments.id"), nullable=False, index=True
    )

    # Convenience copy for UI (the real filename lives on Attachment).
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Parsed header metadata (account, bank, range, etc.) + raw header lines.
    statement_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Computed from imported transaction rows (min/max value_date).
    range_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    range_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_by_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    attachment: Mapped["Attachment"] = relationship("Attachment")
    import_transactions: Mapped[list["BankStatementImportTransaction"]] = relationship(
        "BankStatementImportTransaction",
        back_populates="statement_import",
        cascade="all, delete-orphan",
    )


class BankTransaction(Base):
    """Canonical transaction record, de-duplicated across overlapping imports."""

    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)

    account_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(20), nullable=False, default="KES")

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    debit_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    credit_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Signed amount: debit is negative, credit is positive.
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, index=True)

    account_owner_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    txn_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    seen_in_imports: Mapped[list["BankStatementImportTransaction"]] = relationship(
        "BankStatementImportTransaction",
        back_populates="bank_transaction",
        cascade="all, delete-orphan",
    )
    match: Mapped["BankTransactionMatch | None"] = relationship(
        "BankTransactionMatch",
        back_populates="bank_transaction",
        cascade="all, delete-orphan",
        uselist=False,
    )


class BankStatementImportTransaction(Base):
    """One row from a specific import that references a canonical BankTransaction."""

    __tablename__ = "bank_statement_import_transactions"
    __table_args__ = (
        UniqueConstraint("import_id", "row_index", name="uq_bank_stmt_import_row"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bank_statement_imports.id"), nullable=False, index=True
    )
    bank_transaction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bank_transactions.id"), nullable=False, index=True
    )

    # 1-based row index inside the CSV transaction section (after the header row).
    row_index: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Raw row values as received from CSV (header->cell string).
    raw_row: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    statement_import: Mapped["BankStatementImport"] = relationship(
        "BankStatementImport", back_populates="import_transactions"
    )
    bank_transaction: Mapped["BankTransaction"] = relationship(
        "BankTransaction", back_populates="seen_in_imports"
    )


class BankTransactionMatch(Base):
    """Match between a bank transaction and an internal payment/payout."""

    __tablename__ = "bank_transaction_matches"
    __table_args__ = (
        UniqueConstraint("bank_transaction_id", name="uq_bank_txn_match_txn"),
        UniqueConstraint(
            "procurement_payment_id", name="uq_bank_txn_match_proc_payment"
        ),
        UniqueConstraint(
            "compensation_payout_id", name="uq_bank_txn_match_comp_payout"
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    bank_transaction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bank_transactions.id"), nullable=False, index=True
    )

    procurement_payment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("procurement_payments.id"), nullable=True, index=True
    )
    compensation_payout_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("compensation_payouts.id"), nullable=True, index=True
    )

    match_method: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )

    matched_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True, index=True
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    bank_transaction: Mapped["BankTransaction"] = relationship(
        "BankTransaction", back_populates="match"
    )
    procurement_payment: Mapped["ProcurementPayment | None"] = relationship(
        "ProcurementPayment", foreign_keys=[procurement_payment_id]
    )
    compensation_payout: Mapped["CompensationPayout | None"] = relationship(
        "CompensationPayout", foreign_keys=[compensation_payout_id]
    )

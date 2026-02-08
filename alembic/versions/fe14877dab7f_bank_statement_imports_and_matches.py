"""bank statement imports and matches

Revision ID: fe14877dab7f
Revises: 025
Create Date: 2026-02-06 14:24:47.107302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe14877dab7f'
down_revision: Union[str, None] = '025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("attachment_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index(
        "ix_bank_statement_imports_attachment_id",
        "bank_statement_imports",
        ["attachment_id"],
    )
    op.create_index(
        "ix_bank_statement_imports_created_by_id",
        "bank_statement_imports",
        ["created_by_id"],
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_no", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.String(length=20), nullable=False, server_default=sa.text("'KES'")),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("debit_raw", sa.String(length=200), nullable=True),
        sa.Column("credit_raw", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("account_owner_reference", sa.String(length=300), nullable=True),
        sa.Column("txn_type", sa.String(length=50), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_bank_transactions_fingerprint"),
    )
    op.create_index("ix_bank_transactions_account_no", "bank_transactions", ["account_no"])
    op.create_index("ix_bank_transactions_currency", "bank_transactions", ["currency"])
    op.create_index("ix_bank_transactions_transaction_date", "bank_transactions", ["transaction_date"])
    op.create_index("ix_bank_transactions_value_date", "bank_transactions", ["value_date"])
    op.create_index("ix_bank_transactions_amount", "bank_transactions", ["amount"])
    op.create_index("ix_bank_transactions_fingerprint", "bank_transactions", ["fingerprint"])

    op.create_table(
        "bank_statement_import_transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("import_id", sa.BigInteger(), nullable=False),
        sa.Column("bank_transaction_id", sa.BigInteger(), nullable=False),
        sa.Column("row_index", sa.BigInteger(), nullable=False),
        sa.Column("raw_row", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["bank_statement_imports.id"]),
        sa.ForeignKeyConstraint(["bank_transaction_id"], ["bank_transactions.id"]),
        sa.UniqueConstraint("import_id", "row_index", name="uq_bank_stmt_import_row"),
    )
    op.create_index(
        "ix_bank_statement_import_transactions_import_id",
        "bank_statement_import_transactions",
        ["import_id"],
    )
    op.create_index(
        "ix_bank_statement_import_transactions_bank_transaction_id",
        "bank_statement_import_transactions",
        ["bank_transaction_id"],
    )

    op.create_table(
        "bank_transaction_matches",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("bank_transaction_id", sa.BigInteger(), nullable=False),
        sa.Column("procurement_payment_id", sa.BigInteger(), nullable=True),
        sa.Column("compensation_payout_id", sa.BigInteger(), nullable=True),
        sa.Column("match_method", sa.String(length=20), nullable=False, server_default=sa.text("'auto'")),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("matched_by_id", sa.BigInteger(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bank_transaction_id"], ["bank_transactions.id"]),
        sa.ForeignKeyConstraint(["procurement_payment_id"], ["procurement_payments.id"]),
        sa.ForeignKeyConstraint(["compensation_payout_id"], ["compensation_payouts.id"]),
        sa.ForeignKeyConstraint(["matched_by_id"], ["users.id"]),
        sa.UniqueConstraint("bank_transaction_id", name="uq_bank_txn_match_txn"),
        sa.UniqueConstraint("procurement_payment_id", name="uq_bank_txn_match_proc_payment"),
        sa.UniqueConstraint("compensation_payout_id", name="uq_bank_txn_match_comp_payout"),
    )
    op.create_index(
        "ix_bank_transaction_matches_bank_transaction_id",
        "bank_transaction_matches",
        ["bank_transaction_id"],
    )
    op.create_index(
        "ix_bank_transaction_matches_procurement_payment_id",
        "bank_transaction_matches",
        ["procurement_payment_id"],
    )
    op.create_index(
        "ix_bank_transaction_matches_compensation_payout_id",
        "bank_transaction_matches",
        ["compensation_payout_id"],
    )
    op.create_index(
        "ix_bank_transaction_matches_matched_by_id",
        "bank_transaction_matches",
        ["matched_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_transaction_matches_matched_by_id", table_name="bank_transaction_matches")
    op.drop_index("ix_bank_transaction_matches_compensation_payout_id", table_name="bank_transaction_matches")
    op.drop_index("ix_bank_transaction_matches_procurement_payment_id", table_name="bank_transaction_matches")
    op.drop_index("ix_bank_transaction_matches_bank_transaction_id", table_name="bank_transaction_matches")
    op.drop_table("bank_transaction_matches")

    op.drop_index(
        "ix_bank_statement_import_transactions_bank_transaction_id",
        table_name="bank_statement_import_transactions",
    )
    op.drop_index(
        "ix_bank_statement_import_transactions_import_id",
        table_name="bank_statement_import_transactions",
    )
    op.drop_table("bank_statement_import_transactions")

    op.drop_index("ix_bank_transactions_fingerprint", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_amount", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_value_date", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_transaction_date", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_currency", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_account_no", table_name="bank_transactions")
    op.drop_table("bank_transactions")

    op.drop_index("ix_bank_statement_imports_created_by_id", table_name="bank_statement_imports")
    op.drop_index("ix_bank_statement_imports_attachment_id", table_name="bank_statement_imports")
    op.drop_table("bank_statement_imports")

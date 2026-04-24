"""045 - budget advances and pre-funded employee spending.

Revision ID: 045
Revises: 044
Create Date: 2026-04-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("budget_number", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("purpose_id", sa.BigInteger(), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("approved_by_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["purpose_id"], ["payment_purposes.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.UniqueConstraint("budget_number", name="uq_budgets_budget_number"),
    )
    op.create_index("ix_budgets_budget_number", "budgets", ["budget_number"], unique=False)
    op.create_index("ix_budgets_purpose_id", "budgets", ["purpose_id"], unique=False)
    op.create_index("ix_budgets_period_from", "budgets", ["period_from"], unique=False)
    op.create_index("ix_budgets_period_to", "budgets", ["period_to"], unique=False)
    op.create_index("ix_budgets_status", "budgets", ["status"], unique=False)

    op.create_table(
        "budget_advances",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("advance_number", sa.String(length=50), nullable=False),
        sa.Column("budget_id", sa.BigInteger(), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("amount_issued", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=200), nullable=True),
        sa.Column("proof_text", sa.Text(), nullable=True),
        sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="cash_issue"),
        sa.Column("settlement_due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("advance_number", name="uq_budget_advances_advance_number"),
    )
    op.create_index("ix_budget_advances_advance_number", "budget_advances", ["advance_number"], unique=False)
    op.create_index("ix_budget_advances_budget_id", "budget_advances", ["budget_id"], unique=False)
    op.create_index("ix_budget_advances_employee_id", "budget_advances", ["employee_id"], unique=False)
    op.create_index("ix_budget_advances_issue_date", "budget_advances", ["issue_date"], unique=False)
    op.create_index("ix_budget_advances_settlement_due_date", "budget_advances", ["settlement_due_date"], unique=False)
    op.create_index("ix_budget_advances_status", "budget_advances", ["status"], unique=False)

    op.create_table(
        "budget_advance_returns",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("return_number", sa.String(length=50), nullable=False),
        sa.Column("advance_id", sa.BigInteger(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("return_method", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=200), nullable=True),
        sa.Column("proof_text", sa.Text(), nullable=True),
        sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["advance_id"], ["budget_advances.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("return_number", name="uq_budget_advance_returns_return_number"),
    )
    op.create_index("ix_budget_advance_returns_return_number", "budget_advance_returns", ["return_number"], unique=False)
    op.create_index("ix_budget_advance_returns_advance_id", "budget_advance_returns", ["advance_id"], unique=False)
    op.create_index("ix_budget_advance_returns_return_date", "budget_advance_returns", ["return_date"], unique=False)

    op.create_table(
        "budget_advance_transfers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("transfer_number", sa.String(length=50), nullable=False),
        sa.Column("from_advance_id", sa.BigInteger(), nullable=False),
        sa.Column("to_budget_id", sa.BigInteger(), nullable=False),
        sa.Column("to_employee_id", sa.BigInteger(), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("transfer_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_to_advance_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["from_advance_id"], ["budget_advances.id"]),
        sa.ForeignKeyConstraint(["to_budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["to_employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_to_advance_id"], ["budget_advances.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("transfer_number", name="uq_budget_advance_transfers_transfer_number"),
    )
    op.create_index("ix_budget_advance_transfers_transfer_number", "budget_advance_transfers", ["transfer_number"], unique=False)
    op.create_index("ix_budget_advance_transfers_from_advance_id", "budget_advance_transfers", ["from_advance_id"], unique=False)
    op.create_index("ix_budget_advance_transfers_to_budget_id", "budget_advance_transfers", ["to_budget_id"], unique=False)
    op.create_index("ix_budget_advance_transfers_to_employee_id", "budget_advance_transfers", ["to_employee_id"], unique=False)
    op.create_index("ix_budget_advance_transfers_transfer_date", "budget_advance_transfers", ["transfer_date"], unique=False)
    op.create_index("ix_budget_advance_transfers_created_to_advance_id", "budget_advance_transfers", ["created_to_advance_id"], unique=False)

    op.create_table(
        "budget_claim_allocations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("advance_id", sa.BigInteger(), nullable=False),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("allocation_status", sa.String(length=20), nullable=False, server_default="reserved"),
        sa.Column("released_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["advance_id"], ["budget_advances.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"]),
    )
    op.create_index("ix_budget_claim_allocations_advance_id", "budget_claim_allocations", ["advance_id"], unique=False)
    op.create_index("ix_budget_claim_allocations_claim_id", "budget_claim_allocations", ["claim_id"], unique=False)
    op.create_index("ix_budget_claim_allocations_allocation_status", "budget_claim_allocations", ["allocation_status"], unique=False)

    with op.batch_alter_table("expense_claims") as batch:
        batch.add_column(sa.Column("budget_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("funding_source", sa.String(length=20), nullable=False, server_default="personal_funds"))
        batch.add_column(sa.Column("budget_funding_status", sa.String(length=20), nullable=False, server_default="none"))
        batch.create_foreign_key("fk_expense_claims_budget_id_budgets", "budgets", ["budget_id"], ["id"])
        batch.create_index("ix_expense_claims_budget_id", ["budget_id"], unique=False)
        batch.create_index("ix_expense_claims_funding_source", ["funding_source"], unique=False)

    with op.batch_alter_table("procurement_payments") as batch:
        batch.add_column(sa.Column("budget_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("funding_source", sa.String(length=20), nullable=False, server_default="personal_funds"))
        batch.create_foreign_key("fk_procurement_payments_budget_id_budgets", "budgets", ["budget_id"], ["id"])
        batch.create_index("ix_procurement_payments_budget_id", ["budget_id"], unique=False)
        batch.create_index("ix_procurement_payments_funding_source", ["funding_source"], unique=False)

    with op.batch_alter_table("bank_transaction_matches") as batch:
        batch.add_column(sa.Column("budget_advance_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("budget_advance_return_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_bank_transaction_matches_budget_advance_id_budget_advances",
            "budget_advances",
            ["budget_advance_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_bank_transaction_matches_budget_advance_return_id_budget_advance_returns",
            "budget_advance_returns",
            ["budget_advance_return_id"],
            ["id"],
        )
        batch.create_unique_constraint("uq_bank_txn_match_budget_advance", ["budget_advance_id"])
        batch.create_unique_constraint("uq_bank_txn_match_budget_advance_return", ["budget_advance_return_id"])
        batch.create_index("ix_bank_transaction_matches_budget_advance_id", ["budget_advance_id"], unique=False)
        batch.create_index("ix_bank_transaction_matches_budget_advance_return_id", ["budget_advance_return_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("bank_transaction_matches") as batch:
        batch.drop_index("ix_bank_transaction_matches_budget_advance_return_id")
        batch.drop_index("ix_bank_transaction_matches_budget_advance_id")
        batch.drop_constraint("uq_bank_txn_match_budget_advance_return", type_="unique")
        batch.drop_constraint("uq_bank_txn_match_budget_advance", type_="unique")
        batch.drop_constraint("fk_bank_transaction_matches_budget_advance_return_id_budget_advance_returns", type_="foreignkey")
        batch.drop_constraint("fk_bank_transaction_matches_budget_advance_id_budget_advances", type_="foreignkey")
        batch.drop_column("budget_advance_return_id")
        batch.drop_column("budget_advance_id")

    with op.batch_alter_table("procurement_payments") as batch:
        batch.drop_index("ix_procurement_payments_funding_source")
        batch.drop_index("ix_procurement_payments_budget_id")
        batch.drop_constraint("fk_procurement_payments_budget_id_budgets", type_="foreignkey")
        batch.drop_column("funding_source")
        batch.drop_column("budget_id")

    with op.batch_alter_table("expense_claims") as batch:
        batch.drop_index("ix_expense_claims_funding_source")
        batch.drop_index("ix_expense_claims_budget_id")
        batch.drop_constraint("fk_expense_claims_budget_id_budgets", type_="foreignkey")
        batch.drop_column("budget_funding_status")
        batch.drop_column("funding_source")
        batch.drop_column("budget_id")

    op.drop_index("ix_budget_claim_allocations_allocation_status", table_name="budget_claim_allocations")
    op.drop_index("ix_budget_claim_allocations_claim_id", table_name="budget_claim_allocations")
    op.drop_index("ix_budget_claim_allocations_advance_id", table_name="budget_claim_allocations")
    op.drop_table("budget_claim_allocations")

    op.drop_index("ix_budget_advance_transfers_created_to_advance_id", table_name="budget_advance_transfers")
    op.drop_index("ix_budget_advance_transfers_transfer_date", table_name="budget_advance_transfers")
    op.drop_index("ix_budget_advance_transfers_to_employee_id", table_name="budget_advance_transfers")
    op.drop_index("ix_budget_advance_transfers_to_budget_id", table_name="budget_advance_transfers")
    op.drop_index("ix_budget_advance_transfers_from_advance_id", table_name="budget_advance_transfers")
    op.drop_index("ix_budget_advance_transfers_transfer_number", table_name="budget_advance_transfers")
    op.drop_table("budget_advance_transfers")

    op.drop_index("ix_budget_advance_returns_return_date", table_name="budget_advance_returns")
    op.drop_index("ix_budget_advance_returns_advance_id", table_name="budget_advance_returns")
    op.drop_index("ix_budget_advance_returns_return_number", table_name="budget_advance_returns")
    op.drop_table("budget_advance_returns")

    op.drop_index("ix_budget_advances_status", table_name="budget_advances")
    op.drop_index("ix_budget_advances_settlement_due_date", table_name="budget_advances")
    op.drop_index("ix_budget_advances_issue_date", table_name="budget_advances")
    op.drop_index("ix_budget_advances_employee_id", table_name="budget_advances")
    op.drop_index("ix_budget_advances_budget_id", table_name="budget_advances")
    op.drop_index("ix_budget_advances_advance_number", table_name="budget_advances")
    op.drop_table("budget_advances")

    op.drop_index("ix_budgets_status", table_name="budgets")
    op.drop_index("ix_budgets_period_to", table_name="budgets")
    op.drop_index("ix_budgets_period_from", table_name="budgets")
    op.drop_index("ix_budgets_purpose_id", table_name="budgets")
    op.drop_index("ix_budgets_budget_number", table_name="budgets")
    op.drop_table("budgets")

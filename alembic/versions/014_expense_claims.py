"""014 - Add expense claims and payment proof fields

Revision ID: 014
Revises: 013
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("procurement_payments", sa.Column("proof_text", sa.Text(), nullable=True))
    op.add_column("procurement_payments", sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True))

    op.create_table(
        "expense_claims",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("claim_number", sa.String(length=50), nullable=False),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_approval"),
        sa.Column("paid_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("remaining_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("auto_created_from_payment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("related_procurement_payment_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["procurement_payments.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["purpose_id"], ["payment_purposes.id"]),
        sa.UniqueConstraint("payment_id", name="uq_expense_claims_payment_id"),
    )
    op.create_index("ix_expense_claims_claim_number", "expense_claims", ["claim_number"], unique=True)
    op.create_index("ix_expense_claims_employee_id", "expense_claims", ["employee_id"])
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"])

    op.create_table(
        "compensation_payouts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("payout_number", sa.String(length=50), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("payout_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=200), nullable=True),
        sa.Column("proof_text", sa.Text(), nullable=True),
        sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
    )
    op.create_index("ix_compensation_payouts_payout_number", "compensation_payouts", ["payout_number"], unique=True)
    op.create_index("ix_compensation_payouts_employee_id", "compensation_payouts", ["employee_id"])

    op.create_table(
        "payout_allocations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("payout_id", sa.BigInteger(), nullable=False),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["payout_id"], ["compensation_payouts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"]),
    )
    op.create_index("ix_payout_allocations_payout_id", "payout_allocations", ["payout_id"])
    op.create_index("ix_payout_allocations_claim_id", "payout_allocations", ["claim_id"])

    op.create_table(
        "employee_balances",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("total_approved", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total_paid", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("balance", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"]),
        sa.UniqueConstraint("employee_id", name="uq_employee_balances_employee_id"),
    )
    op.create_index("ix_employee_balances_employee_id", "employee_balances", ["employee_id"])


def downgrade() -> None:
    op.drop_index("ix_employee_balances_employee_id", table_name="employee_balances")
    op.drop_table("employee_balances")

    op.drop_index("ix_payout_allocations_claim_id", table_name="payout_allocations")
    op.drop_index("ix_payout_allocations_payout_id", table_name="payout_allocations")
    op.drop_table("payout_allocations")

    op.drop_index("ix_compensation_payouts_employee_id", table_name="compensation_payouts")
    op.drop_index("ix_compensation_payouts_payout_number", table_name="compensation_payouts")
    op.drop_table("compensation_payouts")
    op.drop_index("ix_expense_claims_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_employee_id", table_name="expense_claims")
    op.drop_index("ix_expense_claims_claim_number", table_name="expense_claims")
    op.drop_table("expense_claims")

    op.drop_column("procurement_payments", "proof_attachment_id")
    op.drop_column("procurement_payments", "proof_text")

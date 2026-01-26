"""008 - Payments and Credit Allocations

Revision ID: 008
Revises: 007
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007_discounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Payments table
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("payment_number", sa.String(50), nullable=False),
        sa.Column("receipt_number", sa.String(50), nullable=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("received_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["received_by_id"], ["users.id"]),
    )
    op.create_index("ix_payments_payment_number", "payments", ["payment_number"], unique=True)
    op.create_index("ix_payments_receipt_number", "payments", ["receipt_number"], unique=True)
    op.create_index("ix_payments_student_id", "payments", ["student_id"])
    op.create_index("ix_payments_status", "payments", ["status"])

    # Credit Allocations table
    op.create_table(
        "credit_allocations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_line_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("allocated_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"]),
        sa.ForeignKeyConstraint(["allocated_by_id"], ["users.id"]),
    )
    op.create_index("ix_credit_allocations_student_id", "credit_allocations", ["student_id"])
    op.create_index("ix_credit_allocations_invoice_id", "credit_allocations", ["invoice_id"])
    op.create_index("ix_credit_allocations_created_at", "credit_allocations", ["created_at"])


def downgrade() -> None:
    op.drop_table("credit_allocations")
    op.drop_table("payments")

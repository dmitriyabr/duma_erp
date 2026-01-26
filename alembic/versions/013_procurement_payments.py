"""013 - Add procurement payments and payment purposes

Revision ID: 013
Revises: 012
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_purposes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_payment_purposes_name", "payment_purposes", ["name"], unique=True)

    op.add_column("purchase_orders", sa.Column("purpose_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_purchase_orders_purpose_id",
        "purchase_orders",
        "payment_purposes",
        ["purpose_id"],
        ["id"],
    )

    op.create_table(
        "procurement_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("payment_number", sa.String(length=50), nullable=False),
        sa.Column("po_id", sa.BigInteger(), nullable=True),
        sa.Column("purpose_id", sa.BigInteger(), nullable=False),
        sa.Column("payee_name", sa.String(length=300), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=200), nullable=True),
        sa.Column("company_paid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("employee_paid_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="posted"),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_by_id", sa.BigInteger(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["purpose_id"], ["payment_purposes.id"]),
        sa.ForeignKeyConstraint(["employee_paid_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_id"], ["users.id"]),
    )
    op.create_index("ix_procurement_payments_payment_number", "procurement_payments", ["payment_number"], unique=True)
    op.create_index("ix_procurement_payments_po_id", "procurement_payments", ["po_id"])
    op.create_index("ix_procurement_payments_status", "procurement_payments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_procurement_payments_status", table_name="procurement_payments")
    op.drop_index("ix_procurement_payments_po_id", table_name="procurement_payments")
    op.drop_index("ix_procurement_payments_payment_number", table_name="procurement_payments")
    op.drop_table("procurement_payments")

    op.drop_constraint("fk_purchase_orders_purpose_id", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "purpose_id")

    op.drop_index("ix_payment_purposes_name", table_name="payment_purposes")
    op.drop_table("payment_purposes")

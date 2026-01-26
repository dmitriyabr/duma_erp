"""011 - Add purchase orders

Revision ID: 011
Revises: 010
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column("supplier_name", sa.String(length=300), nullable=False),
        sa.Column("supplier_contact", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("track_to_warehouse", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expected_total", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("received_value", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("paid_total", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("debt_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])
    op.create_index("ix_purchase_orders_po_number", "purchase_orders", ["po_number"], unique=True)
    op.create_index("ix_purchase_orders_supplier_name", "purchase_orders", ["supplier_name"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("po_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity_expected", sa.Integer(), nullable=False),
        sa.Column("quantity_cancelled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("quantity_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("line_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
    )
    op.create_index("ix_purchase_order_lines_po_id", "purchase_order_lines", ["po_id"])
    op.create_index("ix_purchase_order_lines_item_id", "purchase_order_lines", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_order_lines_item_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_po_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")

    op.drop_index("ix_purchase_orders_supplier_name", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_po_number", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_table("purchase_orders")

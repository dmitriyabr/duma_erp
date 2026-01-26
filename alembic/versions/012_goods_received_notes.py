"""012 - Add goods received notes

Revision ID: 012
Revises: 011
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goods_received_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("grn_number", sa.String(length=50), nullable=False),
        sa.Column("po_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("received_by_id", sa.BigInteger(), nullable=False),
        sa.Column("approved_by_id", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["received_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
    )
    op.create_index("ix_goods_received_notes_grn_number", "goods_received_notes", ["grn_number"], unique=True)
    op.create_index("ix_goods_received_notes_status", "goods_received_notes", ["status"])
    op.create_index("ix_goods_received_notes_po_id", "goods_received_notes", ["po_id"])

    op.create_table(
        "goods_received_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("grn_id", sa.BigInteger(), nullable=False),
        sa.Column("po_line_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["grn_id"], ["goods_received_notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_line_id"], ["purchase_order_lines.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
    )
    op.create_index("ix_goods_received_lines_grn_id", "goods_received_lines", ["grn_id"])


def downgrade() -> None:
    op.drop_index("ix_goods_received_lines_grn_id", table_name="goods_received_lines")
    op.drop_table("goods_received_lines")

    op.drop_index("ix_goods_received_notes_po_id", table_name="goods_received_notes")
    op.drop_index("ix_goods_received_notes_status", table_name="goods_received_notes")
    op.drop_index("ix_goods_received_notes_grn_number", table_name="goods_received_notes")
    op.drop_table("goods_received_notes")

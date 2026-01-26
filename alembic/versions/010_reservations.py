"""010 - Add reservations and reservation items

Revision ID: 010
Revises: 009
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_line_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("invoice_line_id", name="uq_reservations_invoice_line_id"),
    )
    op.create_index("ix_reservations_student_id", "reservations", ["student_id"])
    op.create_index("ix_reservations_invoice_id", "reservations", ["invoice_id"])
    op.create_index("ix_reservations_status", "reservations", ["status"])

    op.create_table(
        "reservation_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reservation_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity_required", sa.Integer(), nullable=False),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_issued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
    )
    op.create_index("ix_reservation_items_reservation_id", "reservation_items", ["reservation_id"])
    op.create_index("ix_reservation_items_item_id", "reservation_items", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_reservation_items_item_id", table_name="reservation_items")
    op.drop_index("ix_reservation_items_reservation_id", table_name="reservation_items")
    op.drop_table("reservation_items")

    op.drop_index("ix_reservations_status", table_name="reservations")
    op.drop_index("ix_reservations_invoice_id", table_name="reservations")
    op.drop_index("ix_reservations_student_id", table_name="reservations")
    op.drop_table("reservations")

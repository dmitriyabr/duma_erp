"""Add inventory tables (stock, stock_movements, issuances)

Revision ID: 004_inventory
Revises: 003_items_categories
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004_inventory"
down_revision: Union[str, None] = "003_items_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Stock table - current stock levels
    op.create_table(
        "stock",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
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
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.UniqueConstraint("item_id"),
    )
    op.create_index("ix_stock_item_id", "stock", ["item_id"], unique=True)

    # Stock movements table - history of all stock changes
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(15, 2), nullable=True),
        sa.Column("quantity_before", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("average_cost_before", sa.Numeric(15, 2), nullable=False),
        sa.Column("average_cost_after", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stock.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_stock_movements_stock_id", "stock_movements", ["stock_id"], unique=False)
    op.create_index("ix_stock_movements_item_id", "stock_movements", ["item_id"], unique=False)
    op.create_index("ix_stock_movements_movement_type", "stock_movements", ["movement_type"], unique=False)
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"], unique=False)

    # Issuances table - unified issuance records
    op.create_table(
        "issuances",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("issuance_number", sa.String(50), nullable=False),
        sa.Column("issuance_type", sa.String(20), nullable=False),  # internal | reservation
        sa.Column("recipient_type", sa.String(20), nullable=False),  # employee | department | student
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        sa.Column("reservation_id", sa.BigInteger(), nullable=True),
        sa.Column("issued_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
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
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"]),
        sa.UniqueConstraint("issuance_number"),
    )
    op.create_index("ix_issuances_issuance_number", "issuances", ["issuance_number"], unique=True)
    op.create_index("ix_issuances_issuance_type", "issuances", ["issuance_type"], unique=False)
    op.create_index("ix_issuances_recipient_id", "issuances", ["recipient_id"], unique=False)
    op.create_index("ix_issuances_reservation_id", "issuances", ["reservation_id"], unique=False)
    op.create_index("ix_issuances_issued_at", "issuances", ["issued_at"], unique=False)

    # Issuance items table
    op.create_table(
        "issuance_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("issuance_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(15, 2), nullable=False),
        sa.Column("reservation_item_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["issuance_id"], ["issuances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
    )
    op.create_index("ix_issuance_items_issuance_id", "issuance_items", ["issuance_id"], unique=False)
    op.create_index("ix_issuance_items_item_id", "issuance_items", ["item_id"], unique=False)


def downgrade() -> None:
    op.drop_table("issuance_items")
    op.drop_table("issuances")
    op.drop_table("stock_movements")
    op.drop_table("stock")

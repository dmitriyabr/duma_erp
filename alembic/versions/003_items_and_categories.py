"""Add items, categories, and kits tables

Revision ID: 003_items_categories
Revises: 002_terms_pricing
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_items_categories"
down_revision: Union[str, None] = "002_terms_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove Diary from fixed_fees (it's an inventory item, not a fee)
    op.execute("DELETE FROM fixed_fees WHERE fee_type = 'Diary'")

    # Categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint("name"),
    )

    # Items table
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("sku_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),  # service | product
        sa.Column("price_type", sa.String(20), nullable=False),  # standard | by_grade | by_zone
        sa.Column("price", sa.Numeric(15, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.UniqueConstraint("sku_code"),
    )
    op.create_index("ix_items_category_id", "items", ["category_id"], unique=False)
    op.create_index("ix_items_item_type", "items", ["item_type"], unique=False)
    op.create_index("ix_items_is_active", "items", ["is_active"], unique=False)

    # Item price history table
    op.create_table(
        "item_price_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("changed_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
    )
    op.create_index("ix_item_price_history_item_id", "item_price_history", ["item_id"], unique=False)

    # Kits table
    op.create_table(
        "kits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sku_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint("sku_code"),
    )

    # Kit items table
    op.create_table(
        "kit_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kit_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["kit_id"], ["kits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.UniqueConstraint("kit_id", "item_id", name="uq_kit_item"),
    )
    op.create_index("ix_kit_items_kit_id", "kit_items", ["kit_id"], unique=False)
    op.create_index("ix_kit_items_item_id", "kit_items", ["item_id"], unique=False)

    # Kit price history table
    op.create_table(
        "kit_price_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kit_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("changed_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["kit_id"], ["kits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
    )
    op.create_index("ix_kit_price_history_kit_id", "kit_price_history", ["kit_id"], unique=False)

    # Seed categories
    op.execute(
        """
        INSERT INTO categories (name, is_active) VALUES
        ('School Fees', true),
        ('Transport', true),
        ('Administrative Fees', true),
        ('Uniform', true),
        ('Books & Stationery', true)
        """
    )

    # Seed items (services)
    # Get category IDs and create items
    op.execute(
        """
        INSERT INTO items (category_id, sku_code, name, item_type, price_type, price, is_active)
        SELECT c.id, 'SCHOOL-FEE', 'School Fee', 'service', 'by_grade', NULL, true
        FROM categories c WHERE c.name = 'School Fees'
        """
    )

    op.execute(
        """
        INSERT INTO items (category_id, sku_code, name, item_type, price_type, price, is_active)
        SELECT c.id, 'TRANSPORT-FEE', 'Transport Fee', 'service', 'by_zone', NULL, true
        FROM categories c WHERE c.name = 'Transport'
        """
    )

    op.execute(
        """
        INSERT INTO items (category_id, sku_code, name, item_type, price_type, price, is_active)
        SELECT c.id, 'ADMISSION-FEE', 'Admission Fee', 'service', 'standard', 5000.00, true
        FROM categories c WHERE c.name = 'Administrative Fees'
        """
    )

    op.execute(
        """
        INSERT INTO items (category_id, sku_code, name, item_type, price_type, price, is_active)
        SELECT c.id, 'INTERVIEW-FEE', 'Interview Fee', 'service', 'standard', 500.00, true
        FROM categories c WHERE c.name = 'Administrative Fees'
        """
    )

    # Create initial price history for items with standard prices
    # Use the first admin user (id=1) as changed_by
    op.execute(
        """
        INSERT INTO item_price_history (item_id, price, changed_by_id)
        SELECT i.id, i.price, 1
        FROM items i
        WHERE i.price IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("kit_price_history")
    op.drop_table("kit_items")
    op.drop_table("kits")
    op.drop_table("item_price_history")
    op.drop_table("items")
    op.drop_table("categories")

    # Restore Diary to fixed_fees
    op.execute(
        """
        INSERT INTO fixed_fees (fee_type, display_name, amount, is_active)
        VALUES ('Diary', 'School Diary', 300.00, true)
        """
    )

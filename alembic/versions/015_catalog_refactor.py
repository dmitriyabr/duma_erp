"""015 - Catalog refactor for kits and invoice lines

Revision ID: 015
Revises: 014
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Kits: add category, item_type, price_type ---
    op.add_column("kits", sa.Column("category_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "kits",
        sa.Column(
            "item_type", sa.String(20), nullable=False, server_default="service"
        ),
    )
    op.add_column(
        "kits",
        sa.Column(
            "price_type", sa.String(20), nullable=False, server_default="standard"
        ),
    )
    op.alter_column("kits", "price", nullable=True)
    op.create_index("ix_kits_category_id", "kits", ["category_id"], unique=False)
    op.create_foreign_key(
        "fk_kits_category_id", "kits", "categories", ["category_id"], ["id"]
    )

    # Ensure Uncategorized category exists for legacy kits
    op.execute(
        """
        INSERT INTO categories (name, is_active)
        SELECT 'Uncategorized', true
        WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Uncategorized')
        """
    )

    # Backfill category_id for existing kits based on kit_items
    op.execute(
        """
        UPDATE kits
        SET category_id = sub.category_id
        FROM (
            SELECT ki.kit_id, MIN(i.category_id) AS category_id
            FROM kit_items ki
            JOIN items i ON i.id = ki.item_id
            GROUP BY ki.kit_id
        ) sub
        WHERE kits.id = sub.kit_id AND kits.category_id IS NULL
        """
    )

    # Assign Uncategorized to any remaining kits
    op.execute(
        """
        UPDATE kits
        SET category_id = (SELECT id FROM categories WHERE name = 'Uncategorized' LIMIT 1)
        WHERE category_id IS NULL
        """
    )

    # Backfill item_type for existing kits
    op.execute(
        """
        UPDATE kits
        SET item_type = 'product'
        WHERE id IN (SELECT DISTINCT kit_id FROM kit_items)
        """
    )
    op.execute(
        """
        UPDATE kits
        SET item_type = 'service'
        WHERE item_type IS NULL
        """
    )

    # --- Create kits for service items and any item used in invoices ---
    op.execute(
        """
        INSERT INTO kits (category_id, sku_code, name, item_type, price_type, price,
                          requires_full_payment, is_active)
        SELECT i.category_id,
               i.sku_code,
               i.name,
               i.item_type,
               i.price_type,
               i.price,
               i.requires_full_payment,
               i.is_active
        FROM items i
        WHERE (i.item_type = 'service'
               OR i.id IN (SELECT DISTINCT item_id FROM invoice_lines WHERE item_id IS NOT NULL))
          AND NOT EXISTS (SELECT 1 FROM kits k WHERE k.sku_code = i.sku_code)
        """
    )

    # Add kit items for product items
    op.execute(
        """
        INSERT INTO kit_items (kit_id, item_id, quantity)
        SELECT k.id, i.id, 1
        FROM items i
        JOIN kits k ON k.sku_code = i.sku_code
        WHERE i.item_type = 'product'
          AND NOT EXISTS (
              SELECT 1 FROM kit_items ki WHERE ki.kit_id = k.id AND ki.item_id = i.id
          )
        """
    )

    # Create kit price history for standard pricing when price is set
    op.execute(
        """
        INSERT INTO kit_price_history (kit_id, price, changed_by_id)
        SELECT k.id, k.price, 1
        FROM kits k
        WHERE k.price IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM kit_price_history h WHERE h.kit_id = k.id)
        """
    )

    # --- Invoice lines: migrate item_id to kit_id and drop item_id ---
    op.execute(
        """
        UPDATE invoice_lines
        SET kit_id = k.id
        FROM items i
        JOIN kits k ON k.sku_code = i.sku_code
        WHERE invoice_lines.item_id = i.id
          AND invoice_lines.kit_id IS NULL
        """
    )

    op.alter_column("invoice_lines", "kit_id", nullable=False)
    op.drop_constraint("invoice_lines_item_id_fkey", "invoice_lines", type_="foreignkey")
    op.drop_column("invoice_lines", "item_id")

    # Remove server defaults on new kit columns
    op.alter_column("kits", "item_type", server_default=None)
    op.alter_column("kits", "price_type", server_default=None)
    op.alter_column("kits", "category_id", nullable=False)


def downgrade() -> None:
    # Restore item_id on invoice_lines
    op.add_column("invoice_lines", sa.Column("item_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "invoice_lines_item_id_fkey", "invoice_lines", "items", ["item_id"], ["id"]
    )
    op.execute(
        """
        UPDATE invoice_lines
        SET item_id = i.id
        FROM kits k
        JOIN items i ON i.sku_code = k.sku_code
        WHERE invoice_lines.kit_id = k.id
          AND invoice_lines.item_id IS NULL
        """
    )
    op.alter_column("invoice_lines", "kit_id", nullable=True)

    # Revert kits schema changes
    op.execute("UPDATE kits SET price = 0 WHERE price IS NULL")
    op.alter_column("kits", "price", nullable=False)
    op.drop_constraint("fk_kits_category_id", "kits", type_="foreignkey")
    op.drop_index("ix_kits_category_id", table_name="kits")
    op.drop_column("kits", "price_type")
    op.drop_column("kits", "item_type")
    op.drop_column("kits", "category_id")

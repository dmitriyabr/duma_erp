"""Refactor variants to many-to-many with source_type in kit_items

Revision ID: 024
Revises: 023
Create Date: 2026-02-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename item_variant_groups to item_variants
    op.rename_table("item_variant_groups", "item_variants")
    
    # 2. Create item_variant_memberships table (many-to-many)
    op.create_table(
        "item_variant_memberships",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "variant_id",
            sa.BigInteger(),
            sa.ForeignKey("item_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_item_variant_memberships_variant_id",
        "item_variant_memberships",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_item_variant_memberships_item_id",
        "item_variant_memberships",
        ["item_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_variant_item",
        "item_variant_memberships",
        ["variant_id", "item_id"],
    )
    
    # 3. Migrate data from items.variant_group_id to item_variant_memberships
    op.execute("""
        INSERT INTO item_variant_memberships (variant_id, item_id, is_default)
        SELECT variant_group_id, id, FALSE
        FROM items
        WHERE variant_group_id IS NOT NULL
    """)
    
    # 4. Drop variant_group_id from items
    op.drop_constraint(
        "fk_items_variant_group_id_item_variant_groups",
        "items",
        type_="foreignkey",
    )
    op.drop_index("ix_items_variant_group_id", table_name="items")
    op.drop_column("items", "variant_group_id")
    
    # 5. Update kit_items: make item_id nullable, add source_type, variant_id, default_item_id
    # First, make item_id nullable (needed for variant source_type)
    op.alter_column("kit_items", "item_id", nullable=True)
    
    # Add new columns
    op.add_column(
        "kit_items",
        sa.Column("source_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "kit_items",
        sa.Column(
            "variant_id",
            sa.BigInteger(),
            sa.ForeignKey("item_variants.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "kit_items",
        sa.Column(
            "default_item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id"),
            nullable=True,
        ),
    )
    
    # Set all existing kit_items to source_type='item'
    op.execute("UPDATE kit_items SET source_type = 'item' WHERE source_type IS NULL")
    
    # Make source_type NOT NULL
    op.alter_column("kit_items", "source_type", nullable=False)
    
    # Add check constraint
    op.create_check_constraint(
        "ck_kit_item_source",
        "kit_items",
        """
        (source_type = 'item' AND item_id IS NOT NULL AND variant_id IS NULL AND default_item_id IS NULL) OR
        (source_type = 'variant' AND variant_id IS NOT NULL AND default_item_id IS NOT NULL AND item_id IS NULL)
        """,
    )
    
    # Add indexes
    op.create_index(
        "ix_kit_items_variant_id",
        "kit_items",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_kit_items_default_item_id",
        "kit_items",
        ["default_item_id"],
        unique=False,
    )


def downgrade() -> None:
    # Remove indexes
    op.drop_index("ix_kit_items_default_item_id", table_name="kit_items")
    op.drop_index("ix_kit_items_variant_id", table_name="kit_items")
    
    # Remove check constraint
    op.drop_constraint("ck_kit_item_source", "kit_items", type_="check")
    
    # Remove new columns from kit_items
    op.drop_column("kit_items", "default_item_id")
    op.drop_column("kit_items", "variant_id")
    op.drop_column("kit_items", "source_type")
    
    # Restore item_id NOT NULL constraint
    op.alter_column("kit_items", "item_id", nullable=False)
    
    # Restore variant_group_id in items
    op.add_column(
        "items",
        sa.Column("variant_group_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_items_variant_group_id",
        "items",
        ["variant_group_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_items_variant_group_id_item_variant_groups",
        "items",
        "item_variants",
        ["variant_group_id"],
        ["id"],
    )
    
    # Migrate data back (take first variant for each item)
    op.execute("""
        UPDATE items
        SET variant_group_id = (
            SELECT variant_id
            FROM item_variant_memberships
            WHERE item_variant_memberships.item_id = items.id
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM item_variant_memberships
            WHERE item_variant_memberships.item_id = items.id
        )
    """)
    
    # Drop item_variant_memberships
    op.drop_constraint("uq_variant_item", "item_variant_memberships", type_="unique")
    op.drop_index("ix_item_variant_memberships_item_id", table_name="item_variant_memberships")
    op.drop_index("ix_item_variant_memberships_variant_id", table_name="item_variant_memberships")
    op.drop_table("item_variant_memberships")
    
    # Rename back
    op.rename_table("item_variants", "item_variant_groups")


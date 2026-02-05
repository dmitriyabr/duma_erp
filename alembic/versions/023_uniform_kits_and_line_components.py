"""uniform kits: editable components and invoice line components

Revision ID: 023
Revises: 022
Create Date: 2026-02-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "023"
down_revision: Union[str, None] = "384fbe33c787"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Item variant groups
    op.create_table(
        "item_variant_groups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Link items to variant groups
    op.add_column(
        "items",
        sa.Column(
            "variant_group_id",
            sa.BigInteger(),
            nullable=True,
        ),
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
        "item_variant_groups",
        ["variant_group_id"],
        ["id"],
    )

    # Editable components flag on kits
    op.add_column(
        "kits",
        sa.Column(
            "is_editable_components",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Invoice line components table
    op.create_table(
        "invoice_line_components",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "invoice_line_id",
            sa.BigInteger(),
            sa.ForeignKey("invoice_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_invoice_line_components_invoice_line_id",
        "invoice_line_components",
        ["invoice_line_id"],
        unique=False,
    )
    op.create_index(
        "ix_invoice_line_components_item_id",
        "invoice_line_components",
        ["item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_line_components_item_id",
        table_name="invoice_line_components",
    )
    op.drop_index(
        "ix_invoice_line_components_invoice_line_id",
        table_name="invoice_line_components",
    )
    op.drop_table("invoice_line_components")

    op.drop_column("kits", "is_editable_components")

    op.drop_constraint(
        "fk_items_variant_group_id_item_variant_groups",
        "items",
        type_="foreignkey",
    )
    op.drop_index("ix_items_variant_group_id", table_name="items")
    op.drop_column("items", "variant_group_id")

    op.drop_table("item_variant_groups")


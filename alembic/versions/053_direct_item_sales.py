"""053 - support direct item sales.

Revision ID: 053
Revises: 052
Create Date: 2026-09-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "053"
down_revision: str | None = "052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column(
            "is_sellable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_items_is_sellable", "items", ["is_sellable"])

    op.add_column(
        "invoice_lines",
        sa.Column("item_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoice_lines_item_id_items",
        "invoice_lines",
        "items",
        ["item_id"],
        ["id"],
    )
    op.create_index("ix_invoice_lines_item_id", "invoice_lines", ["item_id"])
    op.alter_column(
        "invoice_lines",
        "kit_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_invoice_line_exactly_one_source",
        "invoice_lines",
        "(kit_id IS NOT NULL AND item_id IS NULL) OR (kit_id IS NULL AND item_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invoice_line_exactly_one_source", "invoice_lines", type_="check")
    op.alter_column(
        "invoice_lines",
        "kit_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_index("ix_invoice_lines_item_id", table_name="invoice_lines")
    op.drop_constraint("fk_invoice_lines_item_id_items", "invoice_lines", type_="foreignkey")
    op.drop_column("invoice_lines", "item_id")

    op.drop_index("ix_items_is_sellable", table_name="items")
    op.drop_column("items", "is_sellable")

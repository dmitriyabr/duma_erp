"""034 - Drop quantity_reserved columns (demand-based reservations)

Revision ID: 034
Revises: 033
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stock") as batch:
        batch.drop_column("quantity_reserved")

    with op.batch_alter_table("reservation_items") as batch:
        batch.drop_column("quantity_reserved")


def downgrade() -> None:
    with op.batch_alter_table("stock") as batch:
        batch.add_column(
            sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("reservation_items") as batch:
        batch.add_column(
            sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="0")
        )


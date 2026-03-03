"""035 - Add edit_comment to expense claims

Revision ID: 035
Revises: 034
Create Date: 2026-03-03
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("expense_claims") as batch:
        batch.add_column(sa.Column("edit_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("expense_claims") as batch:
        batch.drop_column("edit_comment")


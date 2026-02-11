"""033 - Reset reserved fields for demand-based reservations

Revision ID: 033
Revises: 032
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE stock SET quantity_reserved = 0 WHERE quantity_reserved <> 0"))
    bind.execute(sa.text("UPDATE reservation_items SET quantity_reserved = 0 WHERE quantity_reserved <> 0"))


def downgrade() -> None:
    # No reliable way to restore historical per-row reserved values.
    pass


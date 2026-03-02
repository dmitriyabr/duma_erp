"""038 - Add salary field to employees

Revision ID: 038
Revises: 037
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "038"
down_revision: str | None = "037"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("salary", sa.Numeric(15, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employees", "salary")

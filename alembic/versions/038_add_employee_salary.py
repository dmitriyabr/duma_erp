"""039 - Add salary field to employees

Revision ID: 039
Revises: 038
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "039"
down_revision: str | None = "038"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("employees")}
    if "salary" not in columns:
        op.add_column(
            "employees",
            sa.Column("salary", sa.Numeric(15, 2), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("employees")}
    if "salary" in columns:
        op.drop_column("employees", "salary")

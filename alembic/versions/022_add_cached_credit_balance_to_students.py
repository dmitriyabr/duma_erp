"""Add cached_credit_balance to students table

Revision ID: 022
Revises: 021
Create Date: 2026-01-31

Cache student credit balance in students table to avoid expensive SUM queries
on every page load. Balance is updated when payments/allocations change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cached_credit_balance column
    op.add_column(
        "students",
        sa.Column(
            "cached_credit_balance",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0.00",
        ),
    )

    # Calculate initial values from existing payments and allocations
    op.execute(text("""
        UPDATE students s
        SET cached_credit_balance = COALESCE(
            (SELECT COALESCE(SUM(amount), 0)
             FROM payments
             WHERE student_id = s.id AND status = 'completed'), 0
        ) - COALESCE(
            (SELECT COALESCE(SUM(amount), 0)
             FROM credit_allocations
             WHERE student_id = s.id), 0
        )
    """))


def downgrade() -> None:
    op.drop_column("students", "cached_credit_balance")


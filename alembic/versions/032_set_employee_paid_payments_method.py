"""032 - Set payment_method='employee' for employee-paid procurement payments

Revision ID: 032
Revises: 031
Create Date: 2026-02-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE procurement_payments
            SET payment_method = 'employee'
            WHERE employee_paid_id IS NOT NULL
              AND payment_method <> 'employee'
            """
        )
    )


def downgrade() -> None:
    # Best-effort: revert to 'cash' (previous default for some backfilled rows).
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE procurement_payments
            SET payment_method = 'cash'
            WHERE employee_paid_id IS NOT NULL
              AND payment_method = 'employee'
            """
        )
    )


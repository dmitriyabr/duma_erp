"""042 - add preferred invoice to payments.

Revision ID: 042
Revises: 041
Create Date: 2026-03-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("preferred_invoice_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        op.f("ix_payments_preferred_invoice_id"),
        "payments",
        ["preferred_invoice_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_payments_preferred_invoice_id_invoices",
        "payments",
        "invoices",
        ["preferred_invoice_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_payments_preferred_invoice_id_invoices",
        "payments",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_payments_preferred_invoice_id"), table_name="payments")
    op.drop_column("payments", "preferred_invoice_id")

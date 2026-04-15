"""044 - drop billing account type.

Revision ID: 044
Revises: 043
Create Date: 2026-04-15 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove the legacy individual/family discriminator."""
    op.drop_index(op.f("ix_billing_accounts_account_type"), table_name="billing_accounts")
    op.drop_column("billing_accounts", "account_type")


def downgrade() -> None:
    """Restore the old discriminator for downgrade compatibility."""
    op.add_column(
        "billing_accounts",
        sa.Column(
            "account_type",
            sa.String(length=20),
            nullable=False,
            server_default="individual",
        ),
    )
    op.create_index(
        op.f("ix_billing_accounts_account_type"),
        "billing_accounts",
        ["account_type"],
        unique=False,
    )

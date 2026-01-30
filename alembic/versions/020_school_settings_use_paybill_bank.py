"""020 - School settings: use_paybill, use_bank_transfer

Revision ID: 020
Revises: 019
Create Date: 2026-01-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "school_settings",
        sa.Column("use_paybill", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "school_settings",
        sa.Column("use_bank_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("school_settings", "use_bank_transfer")
    op.drop_column("school_settings", "use_paybill")

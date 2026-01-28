"""017 - Issuance recipient_id nullable (for recipient_type=other)

Revision ID: 017
Revises: 016
Create Date: 2026-01-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "issuances",
        "recipient_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "issuances",
        "recipient_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

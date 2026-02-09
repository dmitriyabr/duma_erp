"""029 - Add expense_claims.rejection_reason

Historically, rejection reason was appended into `expense_claims.description` as:

    <description>\nRejection reason: <reason>

This migration adds a dedicated nullable column `rejection_reason` and (on PostgreSQL)
attempts to backfill it by splitting existing descriptions.

Revision ID: 029
Revises: 028
Create Date: 2026-02-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expense_claims", sa.Column("rejection_reason", sa.Text(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Backfill: extract "Rejection reason:" suffix into rejection_reason, and trim description.
    op.execute(
        """
UPDATE expense_claims
SET
  rejection_reason = NULLIF(trim(split_part(description, 'Rejection reason:', 2)), ''),
  description = trim(split_part(description, 'Rejection reason:', 1))
WHERE description LIKE '%Rejection reason:%'
  AND (rejection_reason IS NULL OR rejection_reason = '');
        """
    )


def downgrade() -> None:
    op.drop_column("expense_claims", "rejection_reason")


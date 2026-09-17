"""054 - synchronize activity kit availability with activity status.

Revision ID: 054
Revises: 053
Create Date: 2026-09-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "054"
down_revision: str | None = "053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE kits
        SET is_active = (activities.status = 'published')
        FROM activities
        WHERE activities.created_activity_kit_id = kits.id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE kits
        SET is_active = true
        FROM activities
        WHERE activities.created_activity_kit_id = kits.id
        """
    )

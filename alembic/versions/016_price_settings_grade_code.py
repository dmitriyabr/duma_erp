"""016 - Normalize price_settings grade to Grade.code

Revision ID: 016
Revises: 015
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE price_settings ps
        SET grade = g.code
        FROM grades g
        WHERE ps.grade = g.name
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE price_settings ps
        SET grade = g.name
        FROM grades g
        WHERE ps.grade = g.code
        """
    )

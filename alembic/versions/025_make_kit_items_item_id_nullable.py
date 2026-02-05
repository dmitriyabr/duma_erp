"""Make kit_items.item_id nullable for variant source_type

Revision ID: 025
Revises: 024
Create Date: 2026-02-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make item_id nullable in kit_items (needed for variant source_type)
    op.alter_column("kit_items", "item_id", nullable=True)


def downgrade() -> None:
    # Before making NOT NULL, ensure all rows have item_id set
    # Set item_id to default_item_id for variant source_type rows
    op.execute("""
        UPDATE kit_items
        SET item_id = default_item_id
        WHERE source_type = 'variant' AND item_id IS NULL AND default_item_id IS NOT NULL
    """)
    # Make item_id NOT NULL again
    op.alter_column("kit_items", "item_id", nullable=False)


"""Set requires_full_payment=true for Admission and Interview kits

Revision ID: 021
Revises: 4881e412a29d
Create Date: 2026-01-30

Admission and Interview fees must be treated as requires_full in auto-allocation.
They were created as service items (009 only updated 'ADMIN-FEE' typo) and
copied to kits in 015 with requires_full_payment=false. This migration fixes
the kits so the first-priority allocation works correctly.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "021"
down_revision: Union[str, None] = "4881e412a29d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE kits
        SET requires_full_payment = true
        WHERE sku_code IN ('ADMISSION-FEE', 'INTERVIEW-FEE')
    """)


def downgrade() -> None:
    # Revert to false only if we want to undo; typically leave as true
    op.execute("""
        UPDATE kits
        SET requires_full_payment = false
        WHERE sku_code IN ('ADMISSION-FEE', 'INTERVIEW-FEE')
    """)

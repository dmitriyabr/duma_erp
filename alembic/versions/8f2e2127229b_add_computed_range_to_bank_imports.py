"""add computed range to bank imports

Revision ID: 8f2e2127229b
Revises: fe14877dab7f
Create Date: 2026-02-06 15:35:32.120089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2e2127229b'
down_revision: Union[str, None] = 'fe14877dab7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bank_statement_imports", sa.Column("range_from", sa.Date(), nullable=True))
    op.add_column("bank_statement_imports", sa.Column("range_to", sa.Date(), nullable=True))
    op.create_index(
        "ix_bank_statement_imports_range_from",
        "bank_statement_imports",
        ["range_from"],
    )
    op.create_index(
        "ix_bank_statement_imports_range_to",
        "bank_statement_imports",
        ["range_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_statement_imports_range_to", table_name="bank_statement_imports")
    op.drop_index("ix_bank_statement_imports_range_from", table_name="bank_statement_imports")
    op.drop_column("bank_statement_imports", "range_to")
    op.drop_column("bank_statement_imports", "range_from")

"""019 - School settings table (PDF branding, M-Pesa, bank, logo/stamp)

Revision ID: 019
Revises: 018
Create Date: 2026-01-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "school_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_name", sa.String(255), nullable=True),
        sa.Column("school_address", sa.String(500), nullable=True),
        sa.Column("school_phone", sa.String(100), nullable=True),
        sa.Column("school_email", sa.String(255), nullable=True),
        sa.Column("mpesa_business_number", sa.String(50), nullable=True),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("bank_account_name", sa.String(255), nullable=True),
        sa.Column("bank_account_number", sa.String(100), nullable=True),
        sa.Column("bank_branch", sa.String(255), nullable=True),
        sa.Column("bank_swift_code", sa.String(50), nullable=True),
        sa.Column("logo_attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("stamp_attachment_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["logo_attachment_id"],
            ["attachments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["stamp_attachment_id"],
            ["attachments.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_school_settings_logo_attachment_id",
        "school_settings",
        ["logo_attachment_id"],
    )
    op.create_index(
        "ix_school_settings_stamp_attachment_id",
        "school_settings",
        ["stamp_attachment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_school_settings_stamp_attachment_id", "school_settings")
    op.drop_index("ix_school_settings_logo_attachment_id", "school_settings")
    op.drop_table("school_settings")

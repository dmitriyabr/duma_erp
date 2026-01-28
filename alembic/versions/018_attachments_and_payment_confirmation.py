"""018 - Attachments table and payment confirmation_attachment_id

Revision ID: 018
Revises: 017
Create Date: 2026-01-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_attachments_created_by_id", "attachments", ["created_by_id"])

    op.add_column(
        "payments",
        sa.Column("confirmation_attachment_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_confirmation_attachment_id",
        "payments",
        "attachments",
        ["confirmation_attachment_id"],
        ["id"],
    )
    op.create_index(
        "ix_payments_confirmation_attachment_id",
        "payments",
        ["confirmation_attachment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_confirmation_attachment_id", "payments")
    op.drop_constraint("fk_payments_confirmation_attachment_id", "payments", type_="foreignkey")
    op.drop_column("payments", "confirmation_attachment_id")

    op.drop_index("ix_attachments_created_by_id", "attachments")
    op.drop_table("attachments")

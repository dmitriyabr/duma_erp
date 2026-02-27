"""035 - M-Pesa C2B events (idempotency + audit)

Revision ID: 035
Revises: 034
Create Date: 2026-02-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mpesa_c2b_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trans_id", sa.String(length=50), nullable=False),
        sa.Column("business_short_code", sa.String(length=50), nullable=True),
        sa.Column("bill_ref_number", sa.String(length=100), nullable=True),
        sa.Column("derived_student_number", sa.String(length=50), nullable=True),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("trans_time_raw", sa.String(length=32), nullable=True),
        sa.Column("msisdn", sa.String(length=32), nullable=True),
        sa.Column("payer_name", sa.String(length=255), nullable=True),
        sa.Column(
            "raw_payload",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="received"),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("payment_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trans_id", name="uq_mpesa_c2b_events_trans_id"),
    )
    op.create_index("ix_mpesa_c2b_events_trans_id", "mpesa_c2b_events", ["trans_id"], unique=True)
    op.create_index(
        "ix_mpesa_c2b_events_business_short_code",
        "mpesa_c2b_events",
        ["business_short_code"],
        unique=False,
    )
    op.create_index(
        "ix_mpesa_c2b_events_bill_ref_number",
        "mpesa_c2b_events",
        ["bill_ref_number"],
        unique=False,
    )
    op.create_index(
        "ix_mpesa_c2b_events_derived_student_number",
        "mpesa_c2b_events",
        ["derived_student_number"],
        unique=False,
    )
    op.create_index("ix_mpesa_c2b_events_msisdn", "mpesa_c2b_events", ["msisdn"], unique=False)
    op.create_index("ix_mpesa_c2b_events_status", "mpesa_c2b_events", ["status"], unique=False)
    op.create_index("ix_mpesa_c2b_events_payment_id", "mpesa_c2b_events", ["payment_id"], unique=False)
    op.create_index("ix_mpesa_c2b_events_received_at", "mpesa_c2b_events", ["received_at"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_mpesa_reference
            ON payments (reference)
            WHERE payment_method = 'mpesa' AND reference IS NOT NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_payments_mpesa_reference")

    op.drop_table("mpesa_c2b_events")


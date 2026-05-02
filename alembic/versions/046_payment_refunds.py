"""046 - student payment refunds and allocation tracing.

Revision ID: 046
Revises: 045
Create Date: 2026-05-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("credit_allocations") as batch:
        batch.add_column(sa.Column("source_payment_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_credit_allocations_source_payment_id_payments",
            "payments",
            ["source_payment_id"],
            ["id"],
        )
        batch.create_index("ix_credit_allocations_source_payment_id", ["source_payment_id"], unique=False)

    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("billing_account_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("refund_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("refunded_by_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
        sa.ForeignKeyConstraint(["refunded_by_id"], ["users.id"]),
    )
    op.create_index("ix_payment_refunds_payment_id", "payment_refunds", ["payment_id"], unique=False)
    op.create_index("ix_payment_refunds_billing_account_id", "payment_refunds", ["billing_account_id"], unique=False)
    op.create_index("ix_payment_refunds_refund_date", "payment_refunds", ["refund_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_refunds_refund_date", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_billing_account_id", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_payment_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")

    with op.batch_alter_table("credit_allocations") as batch:
        batch.drop_index("ix_credit_allocations_source_payment_id")
        batch.drop_constraint("fk_credit_allocations_source_payment_id_payments", type_="foreignkey")
        batch.drop_column("source_payment_id")

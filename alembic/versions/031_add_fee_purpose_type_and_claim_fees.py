"""031 - Add fee purpose type and expense claim transaction fees

Revision ID: 031
Revises: 030
Create Date: 2026-02-11

Changes:
1) Add `payment_purposes.purpose_type` to distinguish normal expense purposes vs fee purposes.
2) Add `expense_claims.fee_amount` + optional `fee_payment_id` to track reimbursable transaction fees.
3) Seed a default fee purpose: "Transaction Fees" (purpose_type="fee") if not already present.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("payment_purposes") as batch:
        batch.add_column(
            sa.Column(
                "purpose_type",
                sa.String(length=20),
                nullable=False,
                server_default="expense",
            )
        )
        batch.create_index("ix_payment_purposes_purpose_type", ["purpose_type"])

    # Ensure existing rows are "expense" (server_default will cover new rows only).
    bind.execute(sa.text("UPDATE payment_purposes SET purpose_type='expense' WHERE purpose_type IS NULL"))

    # Seed a default fee purpose for transaction fees (id is not hard-coded; code resolves by name).
    existing_fee = bind.execute(
        sa.text(
            "SELECT id FROM payment_purposes WHERE lower(name)=lower(:name) LIMIT 1"
        ),
        {"name": "Transaction Fees"},
    ).fetchone()
    if not existing_fee:
        bind.execute(
            sa.text(
                """
                INSERT INTO payment_purposes (name, is_active, purpose_type)
                VALUES (:name, true, 'fee')
                """
            ),
            {"name": "Transaction Fees"},
        )

    with op.batch_alter_table("expense_claims") as batch:
        batch.add_column(
            sa.Column(
                "fee_amount",
                sa.Numeric(15, 2),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(sa.Column("fee_payment_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key(
            "fk_expense_claims_fee_payment_id_procurement_payments",
            "procurement_payments",
            ["fee_payment_id"],
            ["id"],
        )
        batch.create_index("ix_expense_claims_fee_payment_id", ["fee_payment_id"])


def downgrade() -> None:
    with op.batch_alter_table("expense_claims") as batch:
        batch.drop_index("ix_expense_claims_fee_payment_id")
        batch.drop_constraint(
            "fk_expense_claims_fee_payment_id_procurement_payments", type_="foreignkey"
        )
        batch.drop_column("fee_payment_id")
        batch.drop_column("fee_amount")

    with op.batch_alter_table("payment_purposes") as batch:
        batch.drop_index("ix_payment_purposes_purpose_type")
        batch.drop_column("purpose_type")


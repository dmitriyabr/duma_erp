"""030 - Restore required ExpenseClaim.payment_id and drop claim proof columns

Revision ID: 030
Revises: 029
Create Date: 2026-02-10

Context:
- 026 introduced out-of-pocket claims without ProcurementPayment, and added claim-level proof fields:
  `payee_name`, `proof_text`, `proof_attachment_id`, plus made `payment_id` nullable and removed uniqueness.
- We are reverting to canonicalizing expenses via ProcurementPayment: every ExpenseClaim must have a linked
  ProcurementPayment, and proof/payee live on the payment.

This migration:
1) Backfills missing `payment_id` by creating standalone ProcurementPayment rows for claims where payment_id IS NULL.
2) Makes `expense_claims.payment_id` NOT NULL.
3) Restores unique constraint `uq_expense_claims_payment_id` on `expense_claims.payment_id`.
4) Drops `expense_claims.payee_name`, `expense_claims.proof_text`, `expense_claims.proof_attachment_id`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    expense_claims = sa.table(
        "expense_claims",
        sa.column("id", sa.BigInteger()),
        sa.column("payment_id", sa.BigInteger()),
        sa.column("employee_id", sa.BigInteger()),
        sa.column("purpose_id", sa.BigInteger()),
        sa.column("amount", sa.Numeric(15, 2)),
        sa.column("expense_date", sa.Date()),
        sa.column("payee_name", sa.String(length=300)),
        sa.column("proof_text", sa.Text()),
        sa.column("proof_attachment_id", sa.BigInteger()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    procurement_payments = sa.table(
        "procurement_payments",
        sa.column("id", sa.BigInteger()),
        sa.column("payment_number", sa.String(length=50)),
        sa.column("po_id", sa.BigInteger()),
        sa.column("purpose_id", sa.BigInteger()),
        sa.column("payee_name", sa.String(length=300)),
        sa.column("payment_date", sa.Date()),
        sa.column("amount", sa.Numeric(15, 2)),
        sa.column("payment_method", sa.String(length=20)),
        sa.column("reference_number", sa.String(length=200)),
        sa.column("proof_text", sa.Text()),
        sa.column("proof_attachment_id", sa.BigInteger()),
        sa.column("company_paid", sa.Boolean()),
        sa.column("employee_paid_id", sa.BigInteger()),
        sa.column("status", sa.String(length=20)),
        sa.column("cancelled_reason", sa.Text()),
        sa.column("cancelled_by_id", sa.BigInteger()),
        sa.column("cancelled_at", sa.DateTime(timezone=True)),
        sa.column("created_by_id", sa.BigInteger()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    # Backfill claims without linked payment.
    rows = bind.execute(
        sa.select(
            expense_claims.c.id,
            expense_claims.c.employee_id,
            expense_claims.c.purpose_id,
            expense_claims.c.amount,
            expense_claims.c.expense_date,
            expense_claims.c.payee_name,
            expense_claims.c.proof_text,
            expense_claims.c.proof_attachment_id,
            expense_claims.c.created_at,
        ).where(expense_claims.c.payment_id.is_(None))
    ).all()

    for row in rows:
        claim_id = int(row.id)
        employee_id = int(row.employee_id)
        purpose_id = int(row.purpose_id)
        amount = Decimal(str(row.amount))
        payment_date = row.expense_date
        created_at = row.created_at or datetime.utcnow()

        payment_number = f"PPAY-BF-{claim_id}"
        ins = procurement_payments.insert().values(
            payment_number=payment_number,
            po_id=None,
            purpose_id=purpose_id,
            payee_name=row.payee_name,
            payment_date=payment_date,
            amount=amount,
            payment_method="cash",
            reference_number=None,
            proof_text=row.proof_text,
            proof_attachment_id=row.proof_attachment_id,
            company_paid=False,
            employee_paid_id=employee_id,
            status="posted",
            cancelled_reason=None,
            cancelled_by_id=None,
            cancelled_at=None,
            created_by_id=employee_id,
            created_at=created_at,
            updated_at=created_at,
        )
        result = bind.execute(ins)

        payment_id = None
        try:
            payment_id = result.inserted_primary_key[0]
        except Exception:
            payment_id = None
        if payment_id is None:
            payment_id = bind.execute(
                sa.select(procurement_payments.c.id).where(
                    procurement_payments.c.payment_number == payment_number
                )
            ).scalar_one()

        bind.execute(
            expense_claims.update()
            .where(expense_claims.c.id == claim_id)
            .values(payment_id=payment_id)
        )

    # Sanity: ensure payment_id is unique (required for constraint restore).
    dup = bind.execute(
        sa.text(
            """
            SELECT payment_id
            FROM expense_claims
            WHERE payment_id IS NOT NULL
            GROUP BY payment_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).fetchone()
    if dup:
        raise RuntimeError("expense_claims.payment_id has duplicates; cannot restore unique constraint")

    with op.batch_alter_table("expense_claims") as batch:
        batch.alter_column("payment_id", existing_type=sa.BigInteger(), nullable=False)
        batch.create_unique_constraint("uq_expense_claims_payment_id", ["payment_id"])
        batch.drop_column("proof_attachment_id")
        batch.drop_column("proof_text")
        batch.drop_column("payee_name")


def downgrade() -> None:
    # Re-introduce out-of-pocket columns and make payment_id nullable again.
    with op.batch_alter_table("expense_claims") as batch:
        batch.add_column(sa.Column("payee_name", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("proof_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True))
        batch.drop_constraint("uq_expense_claims_payment_id", type_="unique")
        batch.alter_column("payment_id", existing_type=sa.BigInteger(), nullable=True)


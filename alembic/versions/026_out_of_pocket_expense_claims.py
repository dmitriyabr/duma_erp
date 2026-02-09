"""026 - Out-of-pocket expense claims (direct create + proof fields)

Revision ID: 026
Revises: 8f2e2127229b
Create Date: 2026-02-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "026"
down_revision: Union[str, None] = "8f2e2127229b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Allow ExpenseClaim to exist without ProcurementPayment (out-of-pocket flow).
    # Also add claim-level proof fields so we don't depend on procurement payment fields.
    with op.batch_alter_table("expense_claims") as batch:
        batch.drop_constraint("uq_expense_claims_payment_id", type_="unique")
        batch.alter_column("payment_id", existing_type=sa.BigInteger(), nullable=True)
        batch.add_column(sa.Column("payee_name", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("proof_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("expense_claims") as batch:
        batch.drop_column("proof_attachment_id")
        batch.drop_column("proof_text")
        batch.drop_column("payee_name")
        batch.alter_column("payment_id", existing_type=sa.BigInteger(), nullable=False)
        batch.create_unique_constraint("uq_expense_claims_payment_id", ["payment_id"])


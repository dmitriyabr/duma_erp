"""047 - repair payment refund proof reconciliation schema.

Revision ID: 047
Revises: 046
Create Date: 2026-05-06 00:00:00.000000

This is intentionally idempotent. Revision 046 was expanded during feature
iteration, so environments that had already applied the earlier 046 need this
forward migration to add the columns and match FK that the current code uses.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "047"
down_revision: str | None = "046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _has_foreign_key(
    bind,
    table_name: str,
    constrained_columns: list[str],
    referred_table: str,
) -> bool:
    expected_columns = set(constrained_columns)
    for fk in sa.inspect(bind).get_foreign_keys(table_name):
        if fk.get("referred_table") != referred_table:
            continue
        if set(fk.get("constrained_columns") or []) == expected_columns:
            return True
    return False


def _unique_constraint_names(bind, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "payment_refunds"):
        columns = _column_names(bind, "payment_refunds")
        indexes = _index_names(bind, "payment_refunds")
        has_proof_attachment_fk = _has_foreign_key(
            bind,
            "payment_refunds",
            ["proof_attachment_id"],
            "attachments",
        )

        with op.batch_alter_table("payment_refunds") as batch:
            if "refund_method" not in columns:
                batch.add_column(sa.Column("refund_method", sa.String(length=20), nullable=True))
            if "reference_number" not in columns:
                batch.add_column(sa.Column("reference_number", sa.String(length=200), nullable=True))
            if "proof_text" not in columns:
                batch.add_column(sa.Column("proof_text", sa.Text(), nullable=True))
            if "proof_attachment_id" not in columns:
                batch.add_column(sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True))
            if not has_proof_attachment_fk and "proof_attachment_id" not in columns:
                batch.create_foreign_key(
                    "fk_payment_refunds_proof_attachment_id_attachments",
                    "attachments",
                    ["proof_attachment_id"],
                    ["id"],
                )
            if "ix_payment_refunds_proof_attachment_id" not in indexes:
                batch.create_index(
                    "ix_payment_refunds_proof_attachment_id",
                    ["proof_attachment_id"],
                    unique=False,
                )

        # If the column existed but the FK was missing, create the FK in a
        # separate batch because the guard above only runs inside add-column repair.
        if not _has_foreign_key(
            bind,
            "payment_refunds",
            ["proof_attachment_id"],
            "attachments",
        ):
            with op.batch_alter_table("payment_refunds") as batch:
                batch.create_foreign_key(
                    "fk_payment_refunds_proof_attachment_id_attachments",
                    "attachments",
                    ["proof_attachment_id"],
                    ["id"],
                )

    if _has_table(bind, "bank_transaction_matches"):
        columns = _column_names(bind, "bank_transaction_matches")
        indexes = _index_names(bind, "bank_transaction_matches")
        has_payment_refund_fk = _has_foreign_key(
            bind,
            "bank_transaction_matches",
            ["payment_refund_id"],
            "payment_refunds",
        )
        unique_constraints = _unique_constraint_names(bind, "bank_transaction_matches")

        with op.batch_alter_table("bank_transaction_matches") as batch:
            if "payment_refund_id" not in columns:
                batch.add_column(sa.Column("payment_refund_id", sa.BigInteger(), nullable=True))
            if "ix_bank_transaction_matches_payment_refund_id" not in indexes:
                batch.create_index(
                    "ix_bank_transaction_matches_payment_refund_id",
                    ["payment_refund_id"],
                    unique=False,
                )
            if (
                not has_payment_refund_fk
                and "payment_refund_id" not in columns
            ):
                batch.create_foreign_key(
                    "fk_bank_transaction_matches_payment_refund_id_payment_refunds",
                    "payment_refunds",
                    ["payment_refund_id"],
                    ["id"],
                )
            if "uq_bank_txn_match_payment_refund" not in unique_constraints:
                batch.create_unique_constraint(
                    "uq_bank_txn_match_payment_refund",
                    ["payment_refund_id"],
                )

        if not _has_foreign_key(
            bind,
            "bank_transaction_matches",
            ["payment_refund_id"],
            "payment_refunds",
        ):
            with op.batch_alter_table("bank_transaction_matches") as batch:
                batch.create_foreign_key(
                    "fk_bank_transaction_matches_payment_refund_id_payment_refunds",
                    "payment_refunds",
                    ["payment_refund_id"],
                    ["id"],
                )


def downgrade() -> None:
    # No-op by design. Current 046 already owns these columns for fresh databases;
    # dropping them here would make a downgrade from 047 leave a fresh DB behind
    # the declared 046 schema.
    pass

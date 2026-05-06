"""049 - account-level payment refunds.

Revision ID: 049
Revises: 048
Create Date: 2026-05-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "049"
down_revision: str | None = "048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _unique_constraint_names(bind, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints(table_name)}


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


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "payment_refunds"):
        columns = _column_names(bind, "payment_refunds")
        indexes = _index_names(bind, "payment_refunds")
        unique_constraints = _unique_constraint_names(bind, "payment_refunds")

        with op.batch_alter_table("payment_refunds") as batch:
            if "refund_number" not in columns:
                batch.add_column(sa.Column("refund_number", sa.String(length=50), nullable=True))
            if "ix_payment_refunds_refund_number" not in indexes:
                batch.create_index("ix_payment_refunds_refund_number", ["refund_number"], unique=False)
            if "uq_payment_refunds_refund_number" not in unique_constraints:
                batch.create_unique_constraint("uq_payment_refunds_refund_number", ["refund_number"])
            if "payment_id" in columns:
                batch.alter_column("payment_id", existing_type=sa.BigInteger(), nullable=True)

    if not _has_table(bind, "payment_refund_sources"):
        op.create_table(
            "payment_refund_sources",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("refund_id", sa.BigInteger(), nullable=False),
            sa.Column("payment_id", sa.BigInteger(), nullable=False),
            sa.Column("amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["refund_id"], ["payment_refunds.id"]),
            sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        )
        op.create_index("ix_payment_refund_sources_refund_id", "payment_refund_sources", ["refund_id"])
        op.create_index("ix_payment_refund_sources_payment_id", "payment_refund_sources", ["payment_id"])

    if _has_table(bind, "payment_refund_sources") and _has_table(bind, "payment_refunds"):
        source_count = bind.execute(sa.text("select count(*) from payment_refund_sources")).scalar() or 0
        if source_count == 0:
            bind.execute(
                sa.text(
                    """
                    insert into payment_refund_sources (refund_id, payment_id, amount, created_at)
                    select id, payment_id, amount, created_at
                    from payment_refunds
                    where payment_id is not null
                    """
                )
            )

    if _has_table(bind, "credit_allocation_reversals"):
        columns = _column_names(bind, "credit_allocation_reversals")
        indexes = _index_names(bind, "credit_allocation_reversals")
        has_refund_fk = _has_foreign_key(
            bind,
            "credit_allocation_reversals",
            ["refund_id"],
            "payment_refunds",
        )

        with op.batch_alter_table("credit_allocation_reversals") as batch:
            if "refund_id" not in columns:
                batch.add_column(sa.Column("refund_id", sa.BigInteger(), nullable=True))
            if "ix_credit_allocation_reversals_refund_id" not in indexes:
                batch.create_index("ix_credit_allocation_reversals_refund_id", ["refund_id"])
            if not has_refund_fk and "refund_id" not in columns:
                batch.create_foreign_key(
                    "fk_credit_allocation_reversals_refund_id_payment_refunds",
                    "payment_refunds",
                    ["refund_id"],
                    ["id"],
                )

        if not _has_foreign_key(
            bind,
            "credit_allocation_reversals",
            ["refund_id"],
            "payment_refunds",
        ):
            with op.batch_alter_table("credit_allocation_reversals") as batch:
                batch.create_foreign_key(
                    "fk_credit_allocation_reversals_refund_id_payment_refunds",
                    "payment_refunds",
                    ["refund_id"],
                    ["id"],
                )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "credit_allocation_reversals"):
        with op.batch_alter_table("credit_allocation_reversals") as batch:
            if _has_foreign_key(bind, "credit_allocation_reversals", ["refund_id"], "payment_refunds"):
                batch.drop_constraint(
                    "fk_credit_allocation_reversals_refund_id_payment_refunds",
                    type_="foreignkey",
                )
            if "ix_credit_allocation_reversals_refund_id" in _index_names(bind, "credit_allocation_reversals"):
                batch.drop_index("ix_credit_allocation_reversals_refund_id")
            if "refund_id" in _column_names(bind, "credit_allocation_reversals"):
                batch.drop_column("refund_id")

    if _has_table(bind, "payment_refund_sources"):
        op.drop_index("ix_payment_refund_sources_payment_id", table_name="payment_refund_sources")
        op.drop_index("ix_payment_refund_sources_refund_id", table_name="payment_refund_sources")
        op.drop_table("payment_refund_sources")

    if _has_table(bind, "payment_refunds"):
        with op.batch_alter_table("payment_refunds") as batch:
            if "uq_payment_refunds_refund_number" in _unique_constraint_names(bind, "payment_refunds"):
                batch.drop_constraint("uq_payment_refunds_refund_number", type_="unique")
            if "ix_payment_refunds_refund_number" in _index_names(bind, "payment_refunds"):
                batch.drop_index("ix_payment_refunds_refund_number")
            if "refund_number" in _column_names(bind, "payment_refunds"):
                batch.drop_column("refund_number")
            if "payment_id" in _column_names(bind, "payment_refunds"):
                batch.alter_column("payment_id", existing_type=sa.BigInteger(), nullable=False)

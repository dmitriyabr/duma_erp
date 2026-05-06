"""048 - repair credit allocation reversal schema.

Revision ID: 048
Revises: 047
Create Date: 2026-05-06 00:00:00.000000

Revision 047 was deployed before it included this repair. Environments already
stamped at 047 need a new forward revision so Alembic actually applies the
missing allocation reversal table used by payment refunds.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "048"
down_revision: str | None = "047"
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


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "credit_allocations"):
        columns = _column_names(bind, "credit_allocations")
        indexes = _index_names(bind, "credit_allocations")
        has_source_payment_fk = _has_foreign_key(
            bind,
            "credit_allocations",
            ["source_payment_id"],
            "payments",
        )

        with op.batch_alter_table("credit_allocations") as batch:
            if "source_payment_id" not in columns:
                batch.add_column(sa.Column("source_payment_id", sa.BigInteger(), nullable=True))
            if "ix_credit_allocations_source_payment_id" not in indexes:
                batch.create_index(
                    "ix_credit_allocations_source_payment_id",
                    ["source_payment_id"],
                    unique=False,
                )
            if not has_source_payment_fk and "source_payment_id" not in columns:
                batch.create_foreign_key(
                    "fk_credit_allocations_source_payment_id_payments",
                    "payments",
                    ["source_payment_id"],
                    ["id"],
                )

        if not _has_foreign_key(
            bind,
            "credit_allocations",
            ["source_payment_id"],
            "payments",
        ):
            with op.batch_alter_table("credit_allocations") as batch:
                batch.create_foreign_key(
                    "fk_credit_allocations_source_payment_id_payments",
                    "payments",
                    ["source_payment_id"],
                    ["id"],
                )

    if not _has_table(bind, "credit_allocation_reversals"):
        op.create_table(
            "credit_allocation_reversals",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("credit_allocation_id", sa.BigInteger(), nullable=False),
            sa.Column("amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("reversed_by_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "reversed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["credit_allocation_id"],
                ["credit_allocations.id"],
            ),
            sa.ForeignKeyConstraint(["reversed_by_id"], ["users.id"]),
        )

    if _has_table(bind, "credit_allocation_reversals"):
        indexes = _index_names(bind, "credit_allocation_reversals")
        has_allocation_fk = _has_foreign_key(
            bind,
            "credit_allocation_reversals",
            ["credit_allocation_id"],
            "credit_allocations",
        )
        has_reversed_by_fk = _has_foreign_key(
            bind,
            "credit_allocation_reversals",
            ["reversed_by_id"],
            "users",
        )

        with op.batch_alter_table("credit_allocation_reversals") as batch:
            if "ix_credit_allocation_reversals_credit_allocation_id" not in indexes:
                batch.create_index(
                    "ix_credit_allocation_reversals_credit_allocation_id",
                    ["credit_allocation_id"],
                    unique=False,
                )
            if "ix_credit_allocation_reversals_reversed_at" not in indexes:
                batch.create_index(
                    "ix_credit_allocation_reversals_reversed_at",
                    ["reversed_at"],
                    unique=False,
                )
            if not has_allocation_fk:
                batch.create_foreign_key(
                    "fk_credit_allocation_reversals_credit_allocation_id_credit_allocations",
                    "credit_allocations",
                    ["credit_allocation_id"],
                    ["id"],
                )
            if not has_reversed_by_fk:
                batch.create_foreign_key(
                    "fk_credit_allocation_reversals_reversed_by_id_users",
                    "users",
                    ["reversed_by_id"],
                    ["id"],
                )


def downgrade() -> None:
    # No-op by design. This repair only aligns already-stamped environments
    # with the schema that current application code expects.
    pass

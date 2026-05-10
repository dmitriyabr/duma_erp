"""052 - withdrawal reservation actions.

Revision ID: 052
Revises: 051
Create Date: 2026-05-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "052"
down_revision: str | None = "051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "withdrawal_settlement_reservation_actions"):
        op.create_table(
            "withdrawal_settlement_reservation_actions",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("settlement_id", sa.BigInteger(), nullable=False),
            sa.Column("reservation_id", sa.BigInteger(), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("status_before", sa.String(length=20), nullable=False),
            sa.Column("status_after", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["settlement_id"], ["withdrawal_settlements.id"]),
            sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        )

    indexes = _index_names(bind, "withdrawal_settlement_reservation_actions")
    if "ix_withdrawal_settlement_reservation_actions_settlement_id" not in indexes:
        op.create_index(
            "ix_withdrawal_settlement_reservation_actions_settlement_id",
            "withdrawal_settlement_reservation_actions",
            ["settlement_id"],
        )
    if "ix_withdrawal_settlement_reservation_actions_reservation_id" not in indexes:
        op.create_index(
            "ix_withdrawal_settlement_reservation_actions_reservation_id",
            "withdrawal_settlement_reservation_actions",
            ["reservation_id"],
        )
    if "ix_withdrawal_settlement_reservation_actions_action" not in indexes:
        op.create_index(
            "ix_withdrawal_settlement_reservation_actions_action",
            "withdrawal_settlement_reservation_actions",
            ["action"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "withdrawal_settlement_reservation_actions"):
        op.drop_table("withdrawal_settlement_reservation_actions")

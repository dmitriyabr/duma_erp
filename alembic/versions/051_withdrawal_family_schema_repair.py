"""051 - repair withdrawal family settlement schema.

Revision ID: 051
Revises: 050
Create Date: 2026-05-10 10:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "051"
down_revision: str | None = "050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_info(bind, table_name: str, column_name: str) -> dict | None:
    for column in sa.inspect(bind).get_columns(table_name):
        if column["name"] == column_name:
            return column
    return None


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "withdrawal_settlements"):
        student_id = _column_info(bind, "withdrawal_settlements", "student_id")
        if student_id is not None and not student_id["nullable"]:
            with op.batch_alter_table("withdrawal_settlements") as batch:
                batch.alter_column(
                    "student_id",
                    existing_type=sa.BigInteger(),
                    nullable=True,
                )

    if not _has_table(bind, "withdrawal_settlement_students"):
        op.create_table(
            "withdrawal_settlement_students",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("settlement_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("status_before", sa.String(length=30), nullable=False),
            sa.Column("status_after", sa.String(length=30), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["settlement_id"], ["withdrawal_settlements.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        )

    if _has_table(bind, "withdrawal_settlement_students"):
        indexes = _index_names(bind, "withdrawal_settlement_students")
        if "ix_withdrawal_settlement_students_settlement_id" not in indexes:
            op.create_index(
                "ix_withdrawal_settlement_students_settlement_id",
                "withdrawal_settlement_students",
                ["settlement_id"],
            )
        if "ix_withdrawal_settlement_students_student_id" not in indexes:
            op.create_index(
                "ix_withdrawal_settlement_students_student_id",
                "withdrawal_settlement_students",
                ["student_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "withdrawal_settlement_students"):
        op.drop_table("withdrawal_settlement_students")

    if _has_table(bind, "withdrawal_settlements"):
        student_id = _column_info(bind, "withdrawal_settlements", "student_id")
        if student_id is not None and student_id["nullable"]:
            with op.batch_alter_table("withdrawal_settlements") as batch:
                batch.alter_column(
                    "student_id",
                    existing_type=sa.BigInteger(),
                    nullable=False,
                )

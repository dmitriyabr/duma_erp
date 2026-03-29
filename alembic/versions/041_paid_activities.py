"""041 - paid activities.

Revision ID: 041
Revises: 040
Create Date: 2026-03-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("activity_number", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("activity_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("term_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("audience_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("requires_full_payment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_activity_kit_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_activity_kit_id"], ["kits.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("activity_number"),
    )
    op.create_index(op.f("ix_activities_activity_number"), "activities", ["activity_number"], unique=True)
    op.create_index(op.f("ix_activities_code"), "activities", ["code"], unique=True)
    op.create_index(op.f("ix_activities_status"), "activities", ["status"], unique=False)
    op.create_index(op.f("ix_activities_term_id"), "activities", ["term_id"], unique=False)

    op.create_table(
        "activity_grade_scopes",
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("grade_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grade_id"], ["grades.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "grade_id", name="uq_activity_grade_scope"),
    )
    op.create_index(
        op.f("ix_activity_grade_scopes_activity_id"),
        "activity_grade_scopes",
        ["activity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_grade_scopes_grade_id"),
        "activity_grade_scopes",
        ["grade_id"],
        unique=False,
    )

    op.create_table(
        "activity_participants",
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("selected_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("invoice_line_id", sa.BigInteger(), nullable=True),
        sa.Column("excluded_reason", sa.Text(), nullable=True),
        sa.Column("added_manually", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "student_id", name="uq_activity_participant"),
    )
    op.create_index(
        op.f("ix_activity_participants_activity_id"),
        "activity_participants",
        ["activity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_participants_invoice_id"),
        "activity_participants",
        ["invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_participants_status"),
        "activity_participants",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_participants_student_id"),
        "activity_participants",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_activity_participants_student_id"), table_name="activity_participants")
    op.drop_index(op.f("ix_activity_participants_status"), table_name="activity_participants")
    op.drop_index(op.f("ix_activity_participants_invoice_id"), table_name="activity_participants")
    op.drop_index(op.f("ix_activity_participants_activity_id"), table_name="activity_participants")
    op.drop_table("activity_participants")

    op.drop_index(op.f("ix_activity_grade_scopes_grade_id"), table_name="activity_grade_scopes")
    op.drop_index(op.f("ix_activity_grade_scopes_activity_id"), table_name="activity_grade_scopes")
    op.drop_table("activity_grade_scopes")

    op.drop_index(op.f("ix_activities_term_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_status"), table_name="activities")
    op.drop_index(op.f("ix_activities_code"), table_name="activities")
    op.drop_index(op.f("ix_activities_activity_number"), table_name="activities")
    op.drop_table("activities")

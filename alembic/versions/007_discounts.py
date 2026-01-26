"""Add discounts tables

Revision ID: 007_discounts
Revises: 006_invoices
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007_discounts"
down_revision: Union[str, None] = "006_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Discount Reasons table (справочник причин)
    op.create_table(
        "discount_reasons",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # Seed default discount reasons
    op.execute(
        """
        INSERT INTO discount_reasons (code, name, is_active) VALUES
        ('sibling', 'Sibling Discount', true),
        ('staff', 'Staff Child', true),
        ('promotion', 'Promotion', true),
        ('other', 'Other', true)
        """
    )

    # Student Discounts table (постоянные скидки студентов)
    op.create_table(
        "student_discounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("applies_to", sa.String(20), nullable=False, server_default="school_fee"),
        sa.Column("value_type", sa.String(20), nullable=False),
        sa.Column("value", sa.Numeric(15, 2), nullable=False),
        sa.Column("reason_id", sa.BigInteger(), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["discount_reasons.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index(
        "ix_student_discounts_student_id", "student_discounts", ["student_id"], unique=False
    )

    # Discounts table (применённые скидки на строки счетов)
    op.create_table(
        "discounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_line_id", sa.BigInteger(), nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False),
        sa.Column("value", sa.Numeric(15, 2), nullable=False),
        sa.Column("calculated_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("reason_id", sa.BigInteger(), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("student_discount_id", sa.BigInteger(), nullable=True),
        sa.Column("applied_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["invoice_line_id"], ["invoice_lines.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reason_id"], ["discount_reasons.id"]),
        sa.ForeignKeyConstraint(["student_discount_id"], ["student_discounts.id"]),
        sa.ForeignKeyConstraint(["applied_by_id"], ["users.id"]),
    )
    op.create_index(
        "ix_discounts_invoice_line_id", "discounts", ["invoice_line_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("discounts")
    op.drop_table("student_discounts")
    op.drop_table("discount_reasons")

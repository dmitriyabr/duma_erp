"""Add grades and students tables

Revision ID: 005_students
Revises: 004_inventory
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005_students"
down_revision: Union[str, None] = "004_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Grades table
    op.create_table(
        "grades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint("code"),
    )

    # Seed default grades
    op.execute(
        """
        INSERT INTO grades (code, name, display_order, is_active) VALUES
        ('PG', 'Play Group', 1, true),
        ('PP1', 'Pre-Primary 1', 2, true),
        ('PP2', 'Pre-Primary 2', 3, true),
        ('G1', 'Grade 1', 4, true),
        ('G2', 'Grade 2', 5, true),
        ('G3', 'Grade 3', 6, true),
        ('G4', 'Grade 4', 7, true),
        ('G5', 'Grade 5', 8, true),
        ('G6', 'Grade 6', 9, true)
        """
    )

    # Students table
    op.create_table(
        "students",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("student_number", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("grade_id", sa.BigInteger(), nullable=False),
        sa.Column("transport_zone_id", sa.BigInteger(), nullable=True),
        sa.Column("guardian_name", sa.String(200), nullable=False),
        sa.Column("guardian_phone", sa.String(20), nullable=False),
        sa.Column("guardian_email", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("enrollment_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["grade_id"], ["grades.id"]),
        sa.ForeignKeyConstraint(["transport_zone_id"], ["transport_zones.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("student_number"),
    )
    op.create_index("ix_students_student_number", "students", ["student_number"], unique=True)
    op.create_index("ix_students_grade_id", "students", ["grade_id"], unique=False)
    op.create_index("ix_students_transport_zone_id", "students", ["transport_zone_id"], unique=False)
    op.create_index("ix_students_status", "students", ["status"], unique=False)
    op.create_index("ix_students_last_name", "students", ["last_name"], unique=False)


def downgrade() -> None:
    op.drop_table("students")
    op.drop_table("grades")

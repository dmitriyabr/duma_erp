"""036 - Add employees table

Revision ID: 036
Revises: 035
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "036"
down_revision: str | None = "035"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("employee_number", sa.String(length=50), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("surname", sa.String(length=200), nullable=False),
        sa.Column("first_name", sa.String(length=200), nullable=False),
        sa.Column("second_name", sa.String(length=200), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("marital_status", sa.String(length=50), nullable=True),
        sa.Column("nationality", sa.String(length=100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("mobile_phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("physical_address", sa.Text(), nullable=True),
        sa.Column("town", sa.String(length=200), nullable=True),
        sa.Column("postal_address", sa.String(length=500), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("job_title", sa.String(length=200), nullable=True),
        sa.Column("employee_start_date", sa.Date(), nullable=True),
        sa.Column("national_id_number", sa.String(length=50), nullable=True),
        sa.Column("kra_pin_number", sa.String(length=50), nullable=True),
        sa.Column("nssf_number", sa.String(length=50), nullable=True),
        sa.Column("nhif_number", sa.String(length=100), nullable=True),
        sa.Column("bank_name", sa.String(length=200), nullable=True),
        sa.Column(
            "bank_branch_name",
            sa.String(length=200),
            nullable=True,
        ),
        sa.Column("bank_code", sa.String(length=20), nullable=True),
        sa.Column("branch_code", sa.String(length=20), nullable=True),
        sa.Column("bank_account_number", sa.String(length=50), nullable=True),
        sa.Column("bank_account_holder_name", sa.String(length=200), nullable=True),
        sa.Column("next_of_kin_name", sa.String(length=200), nullable=True),
        sa.Column(
            "next_of_kin_relationship",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("next_of_kin_phone", sa.String(length=50), nullable=True),
        sa.Column("next_of_kin_address", sa.Text(), nullable=True),
        sa.Column(
            "has_mortgage_relief",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "has_insurance_relief",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_employees_employee_number",
        "employees",
        ["employee_number"],
        unique=True,
    )
    op.create_index("ix_employees_user_id", "employees", ["user_id"], unique=True)
    op.create_index("ix_employees_status", "employees", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_employees_status", table_name="employees")
    op.drop_index("ix_employees_user_id", table_name="employees")
    op.drop_index("ix_employees_employee_number", table_name="employees")
    op.drop_table("employees")


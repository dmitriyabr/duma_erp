"""037 - Add attachment fields to employees

Revision ID: 037
Revises: 036
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "037"
down_revision: str | None = "036"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("national_id_attachment_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("kra_pin_attachment_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("nssf_attachment_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("nhif_attachment_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "employees",
        sa.Column("bank_doc_attachment_id", sa.BigInteger(), nullable=True),
    )

    op.create_foreign_key(
        "fk_employees_national_id_attachment",
        "employees",
        "attachments",
        ["national_id_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_employees_kra_pin_attachment",
        "employees",
        "attachments",
        ["kra_pin_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_employees_nssf_attachment",
        "employees",
        "attachments",
        ["nssf_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_employees_nhif_attachment",
        "employees",
        "attachments",
        ["nhif_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_employees_bank_doc_attachment",
        "employees",
        "attachments",
        ["bank_doc_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_employees_bank_doc_attachment",
        "employees",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_employees_nhif_attachment",
        "employees",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_employees_nssf_attachment",
        "employees",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_employees_kra_pin_attachment",
        "employees",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_employees_national_id_attachment",
        "employees",
        type_="foreignkey",
    )

    op.drop_column("employees", "bank_doc_attachment_id")
    op.drop_column("employees", "nhif_attachment_id")
    op.drop_column("employees", "nssf_attachment_id")
    op.drop_column("employees", "kra_pin_attachment_id")
    op.drop_column("employees", "national_id_attachment_id")


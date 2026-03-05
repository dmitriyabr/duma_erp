"""038 - Add attachment fields to employees

Revision ID: 038
Revises: 037
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "038"
down_revision: str | None = "037"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("employees")}

    fk_specs = [
        ("fk_employees_national_id_attachment", "national_id_attachment_id"),
        ("fk_employees_kra_pin_attachment", "kra_pin_attachment_id"),
        ("fk_employees_nssf_attachment", "nssf_attachment_id"),
        ("fk_employees_nhif_attachment", "nhif_attachment_id"),
        ("fk_employees_bank_doc_attachment", "bank_doc_attachment_id"),
    ]

    for fk_name, column_name in fk_specs:
        if fk_name in existing_fks:
            continue
        op.create_foreign_key(
            fk_name,
            "employees",
            "attachments",
            [column_name],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("employees")}

    for fk_name in (
        "fk_employees_bank_doc_attachment",
        "fk_employees_nhif_attachment",
        "fk_employees_nssf_attachment",
        "fk_employees_kra_pin_attachment",
        "fk_employees_national_id_attachment",
    ):
        if fk_name in existing_fks:
            op.drop_constraint(fk_name, "employees", type_="foreignkey")


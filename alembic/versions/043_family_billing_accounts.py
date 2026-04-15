"""043 - family billing accounts.

Revision ID: 043
Revises: 042
Create Date: 2026-04-04
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_accounts",
        sa.Column("account_number", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False, server_default="individual"),
        sa.Column("primary_guardian_name", sa.String(length=200), nullable=True),
        sa.Column("primary_guardian_phone", sa.String(length=20), nullable=True),
        sa.Column("primary_guardian_email", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cached_credit_balance", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_number"),
    )
    op.create_index(
        op.f("ix_billing_accounts_account_number"),
        "billing_accounts",
        ["account_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_billing_accounts_account_type"),
        "billing_accounts",
        ["account_type"],
        unique=False,
    )

    op.add_column("students", sa.Column("billing_account_id", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_students_billing_account_id"),
        "students",
        ["billing_account_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_students_billing_account_id_billing_accounts",
        "students",
        "billing_accounts",
        ["billing_account_id"],
        ["id"],
    )

    op.add_column("invoices", sa.Column("billing_account_id", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_invoices_billing_account_id"),
        "invoices",
        ["billing_account_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_invoices_billing_account_id_billing_accounts",
        "invoices",
        "billing_accounts",
        ["billing_account_id"],
        ["id"],
    )

    op.add_column("payments", sa.Column("billing_account_id", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_payments_billing_account_id"),
        "payments",
        ["billing_account_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_payments_billing_account_id_billing_accounts",
        "payments",
        "billing_accounts",
        ["billing_account_id"],
        ["id"],
    )

    op.add_column("credit_allocations", sa.Column("billing_account_id", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_credit_allocations_billing_account_id"),
        "credit_allocations",
        ["billing_account_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_credit_allocations_billing_account_id_billing_accounts",
        "credit_allocations",
        "billing_accounts",
        ["billing_account_id"],
        ["id"],
    )

    bind = op.get_bind()
    current_year = datetime.utcnow().year

    students = sa.table(
        "students",
        sa.column("id", sa.BigInteger()),
        sa.column("student_number", sa.String()),
        sa.column("first_name", sa.String()),
        sa.column("last_name", sa.String()),
        sa.column("guardian_name", sa.String()),
        sa.column("guardian_phone", sa.String()),
        sa.column("guardian_email", sa.String()),
        sa.column("cached_credit_balance", sa.Numeric(15, 2)),
        sa.column("created_by_id", sa.BigInteger()),
        sa.column("billing_account_id", sa.BigInteger()),
    )
    billing_accounts = sa.table(
        "billing_accounts",
        sa.column("id", sa.BigInteger()),
        sa.column("account_number", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("account_type", sa.String()),
        sa.column("primary_guardian_name", sa.String()),
        sa.column("primary_guardian_phone", sa.String()),
        sa.column("primary_guardian_email", sa.String()),
        sa.column("cached_credit_balance", sa.Numeric(15, 2)),
        sa.column("created_by_id", sa.BigInteger()),
    )
    invoices = sa.table(
        "invoices",
        sa.column("student_id", sa.BigInteger()),
        sa.column("billing_account_id", sa.BigInteger()),
    )
    payments = sa.table(
        "payments",
        sa.column("student_id", sa.BigInteger()),
        sa.column("billing_account_id", sa.BigInteger()),
    )
    credit_allocations = sa.table(
        "credit_allocations",
        sa.column("student_id", sa.BigInteger()),
        sa.column("billing_account_id", sa.BigInteger()),
    )
    document_sequences = sa.table(
        "document_sequences",
        sa.column("id", sa.Integer()),
        sa.column("prefix", sa.String()),
        sa.column("year", sa.Integer()),
        sa.column("last_number", sa.Integer()),
    )

    sequence_row = bind.execute(
        sa.select(document_sequences.c.id, document_sequences.c.last_number).where(
            document_sequences.c.prefix == "FAM",
            document_sequences.c.year == current_year,
        )
    ).mappings().first()

    if sequence_row is None:
        bind.execute(
            sa.insert(document_sequences).values(
                prefix="FAM",
                year=current_year,
                last_number=0,
            )
        )
        last_number = 0
    else:
        last_number = int(sequence_row["last_number"] or 0)

    student_rows = bind.execute(
        sa.select(
            students.c.id,
            students.c.student_number,
            students.c.first_name,
            students.c.last_name,
            students.c.guardian_name,
            students.c.guardian_phone,
            students.c.guardian_email,
            students.c.cached_credit_balance,
            students.c.created_by_id,
        ).order_by(students.c.id)
    ).mappings().all()

    assignments: list[tuple[int, int]] = []
    next_number = last_number
    for row in student_rows:
        next_number += 1
        display_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or row["student_number"]
        account_id = int(
            bind.execute(
                sa.insert(billing_accounts)
                .values(
                    account_number=f"FAM-{current_year}-{next_number:06d}",
                    display_name=display_name,
                    account_type="individual",
                    primary_guardian_name=row["guardian_name"],
                    primary_guardian_phone=row["guardian_phone"],
                    primary_guardian_email=row["guardian_email"],
                    cached_credit_balance=Decimal(str(row["cached_credit_balance"] or 0)),
                    created_by_id=row["created_by_id"],
                )
                .returning(billing_accounts.c.id)
            ).scalar_one()
        )
        assignments.append((int(row["id"]), account_id))

    if next_number != last_number:
        bind.execute(
            sa.update(document_sequences)
            .where(
                document_sequences.c.prefix == "FAM",
                document_sequences.c.year == current_year,
            )
            .values(last_number=next_number)
        )

    for student_id, account_id in assignments:
        bind.execute(
            sa.update(students)
            .where(students.c.id == student_id)
            .values(billing_account_id=account_id)
        )
        bind.execute(
            sa.update(invoices)
            .where(invoices.c.student_id == student_id)
            .values(billing_account_id=account_id)
        )
        bind.execute(
            sa.update(payments)
            .where(payments.c.student_id == student_id)
            .values(billing_account_id=account_id)
        )
        bind.execute(
            sa.update(credit_allocations)
            .where(credit_allocations.c.student_id == student_id)
            .values(billing_account_id=account_id)
        )

    op.alter_column("students", "billing_account_id", nullable=False)
    op.alter_column("invoices", "billing_account_id", nullable=False)
    op.alter_column("payments", "billing_account_id", nullable=False)
    op.alter_column("credit_allocations", "billing_account_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        "fk_credit_allocations_billing_account_id_billing_accounts",
        "credit_allocations",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_credit_allocations_billing_account_id"),
        table_name="credit_allocations",
    )
    op.drop_column("credit_allocations", "billing_account_id")

    op.drop_constraint(
        "fk_payments_billing_account_id_billing_accounts",
        "payments",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_payments_billing_account_id"), table_name="payments")
    op.drop_column("payments", "billing_account_id")

    op.drop_constraint(
        "fk_invoices_billing_account_id_billing_accounts",
        "invoices",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_invoices_billing_account_id"), table_name="invoices")
    op.drop_column("invoices", "billing_account_id")

    op.drop_constraint(
        "fk_students_billing_account_id_billing_accounts",
        "students",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_students_billing_account_id"), table_name="students")
    op.drop_column("students", "billing_account_id")

    op.drop_index(op.f("ix_billing_accounts_account_type"), table_name="billing_accounts")
    op.drop_index(op.f("ix_billing_accounts_account_number"), table_name="billing_accounts")
    op.drop_table("billing_accounts")

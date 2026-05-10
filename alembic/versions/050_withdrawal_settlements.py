"""050 - withdrawal settlements and invoice adjustments.

Revision ID: 050
Revises: 049
Create Date: 2026-05-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "050"
down_revision: str | None = "049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "invoices"):
        columns = _column_names(bind, "invoices")
        with op.batch_alter_table("invoices") as batch:
            if "adjustment_total" not in columns:
                batch.add_column(
                    sa.Column(
                        "adjustment_total",
                        sa.Numeric(15, 2),
                        nullable=False,
                        server_default="0.00",
                    )
                )

    if _has_table(bind, "invoice_lines"):
        columns = _column_names(bind, "invoice_lines")
        with op.batch_alter_table("invoice_lines") as batch:
            if "adjustment_amount" not in columns:
                batch.add_column(
                    sa.Column(
                        "adjustment_amount",
                        sa.Numeric(15, 2),
                        nullable=False,
                        server_default="0.00",
                    )
                )

    if not _has_table(bind, "withdrawal_settlements"):
        op.create_table(
            "withdrawal_settlements",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("settlement_number", sa.String(length=50), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=True),
            sa.Column("billing_account_id", sa.BigInteger(), nullable=False),
            sa.Column("refund_id", sa.BigInteger(), nullable=True),
            sa.Column("settlement_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="posted"),
            sa.Column("retained_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
            sa.Column("deduction_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
            sa.Column("write_off_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
            sa.Column("cancelled_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
            sa.Column("refund_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
            sa.Column(
                "remaining_collectible_debt",
                sa.Numeric(15, 2),
                nullable=False,
                server_default="0.00",
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("proof_attachment_id", sa.BigInteger(), nullable=True),
            sa.Column("created_by_id", sa.BigInteger(), nullable=False),
            sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
            sa.ForeignKeyConstraint(["refund_id"], ["payment_refunds.id"]),
            sa.ForeignKeyConstraint(["proof_attachment_id"], ["attachments.id"]),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.UniqueConstraint("settlement_number", name="uq_withdrawal_settlements_number"),
        )
        op.create_index("ix_withdrawal_settlements_settlement_number", "withdrawal_settlements", ["settlement_number"])
        op.create_index("ix_withdrawal_settlements_student_id", "withdrawal_settlements", ["student_id"])
        op.create_index("ix_withdrawal_settlements_billing_account_id", "withdrawal_settlements", ["billing_account_id"])
        op.create_index("ix_withdrawal_settlements_refund_id", "withdrawal_settlements", ["refund_id"])
        op.create_index("ix_withdrawal_settlements_settlement_date", "withdrawal_settlements", ["settlement_date"])
        op.create_index("ix_withdrawal_settlements_status", "withdrawal_settlements", ["status"])
        op.create_index("ix_withdrawal_settlements_proof_attachment_id", "withdrawal_settlements", ["proof_attachment_id"])

    if not _has_table(bind, "withdrawal_settlement_students"):
        op.create_table(
            "withdrawal_settlement_students",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("settlement_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("status_before", sa.String(length=30), nullable=False),
            sa.Column("status_after", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["settlement_id"], ["withdrawal_settlements.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        )
        op.create_index(
            "ix_withdrawal_settlement_students_settlement_id",
            "withdrawal_settlement_students",
            ["settlement_id"],
        )
        op.create_index(
            "ix_withdrawal_settlement_students_student_id",
            "withdrawal_settlement_students",
            ["student_id"],
        )

    if not _has_table(bind, "withdrawal_settlement_lines"):
        op.create_table(
            "withdrawal_settlement_lines",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("settlement_id", sa.BigInteger(), nullable=False),
            sa.Column("invoice_id", sa.BigInteger(), nullable=True),
            sa.Column("invoice_line_id", sa.BigInteger(), nullable=True),
            sa.Column("action", sa.String(length=30), nullable=False),
            sa.Column("amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["settlement_id"], ["withdrawal_settlements.id"]),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
            sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"]),
        )
        op.create_index("ix_withdrawal_settlement_lines_settlement_id", "withdrawal_settlement_lines", ["settlement_id"])
        op.create_index("ix_withdrawal_settlement_lines_invoice_id", "withdrawal_settlement_lines", ["invoice_id"])
        op.create_index("ix_withdrawal_settlement_lines_invoice_line_id", "withdrawal_settlement_lines", ["invoice_line_id"])
        op.create_index("ix_withdrawal_settlement_lines_action", "withdrawal_settlement_lines", ["action"])

    if not _has_table(bind, "invoice_adjustments"):
        op.create_table(
            "invoice_adjustments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("adjustment_number", sa.String(length=50), nullable=False),
            sa.Column("invoice_id", sa.BigInteger(), nullable=False),
            sa.Column("invoice_line_id", sa.BigInteger(), nullable=True),
            sa.Column("settlement_id", sa.BigInteger(), nullable=True),
            sa.Column("adjustment_type", sa.String(length=30), nullable=False),
            sa.Column("amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
            sa.ForeignKeyConstraint(["invoice_line_id"], ["invoice_lines.id"]),
            sa.ForeignKeyConstraint(["settlement_id"], ["withdrawal_settlements.id"]),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.UniqueConstraint("adjustment_number", name="uq_invoice_adjustments_number"),
        )
        op.create_index("ix_invoice_adjustments_adjustment_number", "invoice_adjustments", ["adjustment_number"])
        op.create_index("ix_invoice_adjustments_invoice_id", "invoice_adjustments", ["invoice_id"])
        op.create_index("ix_invoice_adjustments_invoice_line_id", "invoice_adjustments", ["invoice_line_id"])
        op.create_index("ix_invoice_adjustments_settlement_id", "invoice_adjustments", ["settlement_id"])
        op.create_index("ix_invoice_adjustments_adjustment_type", "invoice_adjustments", ["adjustment_type"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "invoice_adjustments"):
        op.drop_table("invoice_adjustments")
    if _has_table(bind, "withdrawal_settlement_lines"):
        op.drop_table("withdrawal_settlement_lines")
    if _has_table(bind, "withdrawal_settlement_students"):
        op.drop_table("withdrawal_settlement_students")
    if _has_table(bind, "withdrawal_settlements"):
        op.drop_table("withdrawal_settlements")
    if _has_table(bind, "invoice_lines") and "adjustment_amount" in _column_names(bind, "invoice_lines"):
        with op.batch_alter_table("invoice_lines") as batch:
            batch.drop_column("adjustment_amount")
    if _has_table(bind, "invoices") and "adjustment_total" in _column_names(bind, "invoices"):
        with op.batch_alter_table("invoices") as batch:
            batch.drop_column("adjustment_total")

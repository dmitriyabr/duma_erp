"""Add invoices and invoice_lines tables

Revision ID: 006_invoices
Revises: 005_students
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "006_invoices"
down_revision: Union[str, None] = "005_students"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Invoices table
    op.create_table(
        "invoices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("term_id", sa.BigInteger(), nullable=True),
        sa.Column("invoice_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("discount_total", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("total", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("paid_total", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_due", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
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
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"], unique=True)
    op.create_index("ix_invoices_student_id", "invoices", ["student_id"], unique=False)
    op.create_index("ix_invoices_term_id", "invoices", ["term_id"], unique=False)
    op.create_index("ix_invoices_invoice_type", "invoices", ["invoice_type"], unique=False)
    op.create_index("ix_invoices_status", "invoices", ["status"], unique=False)

    # Invoice Lines table
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("kit_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("net_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(15, 2), nullable=False, server_default="0.00"),
        sa.Column("remaining_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["kit_id"], ["kits.id"]),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"], unique=False)


def downgrade() -> None:
    op.drop_table("invoice_lines")
    op.drop_table("invoices")

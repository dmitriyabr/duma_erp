"""Preserve transport price history for cash reports.

Revision ID: 055
Revises: 054
"""

import sqlalchemy as sa

from alembic import op

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transport_repricings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column(
            "invoice_line_id", sa.BigInteger(), sa.ForeignKey("invoice_lines.id"), nullable=False
        ),
        sa.Column("zone_id", sa.BigInteger(), sa.ForeignKey("transport_zones.id"), nullable=False),
        *(
            sa.Column(name, sa.Numeric(15, 2), nullable=False)
            for name in (
                "gross_before",
                "net_before",
                "gross_after",
                "net_after",
                "released_credit",
            )
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transport_repricings_invoice_id", "transport_repricings", ["invoice_id"])


def downgrade():
    op.drop_table("transport_repricings")

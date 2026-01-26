"""Add terms and pricing tables

Revision ID: 002_terms_pricing
Revises: 001_initial
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_terms_pricing"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Terms table
    op.create_table(
        "terms",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("term_number", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("year", "term_number", name="uq_term_year_number"),
    )
    op.create_index("ix_terms_year", "terms", ["year"], unique=False)
    op.create_index("ix_terms_status", "terms", ["status"], unique=False)

    # Transport zones table
    op.create_table(
        "transport_zones",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("zone_name", sa.String(100), nullable=False),
        sa.Column("zone_code", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone_name"),
        sa.UniqueConstraint("zone_code"),
    )

    # Price settings table
    op.create_table(
        "price_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("term_id", sa.BigInteger(), nullable=False),
        sa.Column("grade", sa.String(50), nullable=False),
        sa.Column("school_fee_amount", sa.Numeric(15, 2), nullable=False),
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
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("term_id", "grade", name="uq_price_setting_term_grade"),
    )

    # Transport pricing table
    op.create_table(
        "transport_pricings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("term_id", sa.BigInteger(), nullable=False),
        sa.Column("zone_id", sa.BigInteger(), nullable=False),
        sa.Column("transport_fee_amount", sa.Numeric(15, 2), nullable=False),
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
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["transport_zones.id"]),
        sa.UniqueConstraint("term_id", "zone_id", name="uq_transport_pricing_term_zone"),
    )

    # Fixed fees table
    op.create_table(
        "fixed_fees",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fee_type", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
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
        sa.UniqueConstraint("fee_type"),
    )

    # Seed default fixed fees
    op.execute(
        """
        INSERT INTO fixed_fees (fee_type, display_name, amount, is_active) VALUES
        ('Admission', 'Admission Fee', 5000.00, true),
        ('Interview', 'Interview Fee', 500.00, true),
        ('Diary', 'School Diary', 300.00, true)
        """
    )

    # Seed default transport zones
    op.execute(
        """
        INSERT INTO transport_zones (zone_name, zone_code, is_active) VALUES
        ('Zone A - Nearby', 'ZONE_A', true),
        ('Zone B - Medium', 'ZONE_B', true),
        ('Zone C - Far', 'ZONE_C', true)
        """
    )


def downgrade() -> None:
    op.drop_table("fixed_fees")
    op.drop_table("transport_pricings")
    op.drop_table("price_settings")
    op.drop_table("transport_zones")
    op.drop_table("terms")

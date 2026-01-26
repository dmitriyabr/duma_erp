"""009 - Add requires_full_payment to items and kits

Revision ID: 009
Revises: 008
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add requires_full_payment to items
    # Default False for services, but we'll update products and admission fee after
    op.add_column(
        "items",
        sa.Column("requires_full_payment", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Add requires_full_payment to kits (default True since kits contain products)
    op.add_column(
        "kits",
        sa.Column("requires_full_payment", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Update existing products to require full payment
    op.execute("UPDATE items SET requires_full_payment = true WHERE item_type = 'product'")

    # Update admission fee to require full payment (by sku_code)
    op.execute("UPDATE items SET requires_full_payment = true WHERE sku_code = 'ADMIN-FEE'")


def downgrade() -> None:
    op.drop_column("kits", "requires_full_payment")
    op.drop_column("items", "requires_full_payment")

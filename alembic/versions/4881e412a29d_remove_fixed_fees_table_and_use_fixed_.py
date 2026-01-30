"""Remove fixed_fees table and use Fixed Fees category in kits

Revision ID: 4881e412a29d
Revises: 020
Create Date: 2026-01-30 16:57:51.330461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4881e412a29d'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove fixed_fees table and consolidate with kits table using "Fixed Fees" category.

    1. Create "Fixed Fees" category if not exists
    2. Move ADMISSION-FEE and INTERVIEW-FEE kits to "Fixed Fees" category
    3. Drop fixed_fees table
    """
    # Create connection for raw SQL operations
    conn = op.get_bind()

    # 1. Create "Fixed Fees" category if it doesn't exist
    conn.execute(sa.text("""
        INSERT INTO categories (name, is_active, created_at, updated_at)
        SELECT 'Fixed Fees', true, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM categories WHERE name = 'Fixed Fees'
        )
    """))

    # 2. Get the category_id for "Fixed Fees"
    result = conn.execute(sa.text("SELECT id FROM categories WHERE name = 'Fixed Fees'"))
    fixed_fees_category_id = result.scalar()

    # 3. Update kits with ADMISSION-FEE and INTERVIEW-FEE to use "Fixed Fees" category
    conn.execute(sa.text(f"""
        UPDATE kits
        SET category_id = {fixed_fees_category_id}
        WHERE sku_code IN ('ADMISSION-FEE', 'INTERVIEW-FEE')
    """))

    # 4. Drop fixed_fees table (it's now redundant)
    op.drop_table('fixed_fees')


def downgrade() -> None:
    """
    Restore fixed_fees table and copy data back from kits.
    """
    # Create connection for raw SQL operations
    conn = op.get_bind()

    # 1. Recreate fixed_fees table
    op.create_table(
        'fixed_fees',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('fee_type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fee_type')
    )

    # 2. Copy data back from kits to fixed_fees
    # Map ADMISSION-FEE -> Admission, INTERVIEW-FEE -> Interview
    conn.execute(sa.text("""
        INSERT INTO fixed_fees (fee_type, display_name, amount, is_active, created_at, updated_at)
        SELECT
            CASE
                WHEN sku_code = 'ADMISSION-FEE' THEN 'Admission'
                WHEN sku_code = 'INTERVIEW-FEE' THEN 'Interview'
            END as fee_type,
            name as display_name,
            COALESCE(price, 0) as amount,
            is_active,
            created_at,
            updated_at
        FROM kits
        WHERE sku_code IN ('ADMISSION-FEE', 'INTERVIEW-FEE')
    """))

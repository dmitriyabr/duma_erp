"""add_performance_indexes

Revision ID: 384fbe33c787
Revises: 022
Create Date: 2026-02-01 23:02:24.887221

Add composite indexes and date indexes for performance optimization.
Based on analysis of common query patterns in the codebase.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '384fbe33c787'
down_revision: Union[str, None] = '022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Invoice indexes ===
    
    # Composite index for common invoice filtering pattern:
    # WHERE student_id = ? AND term_id = ? AND invoice_type = ? AND status NOT IN (...)
    # Used in: generate_term_invoices, list_invoices
    op.create_index(
        'ix_invoices_student_term_type_status',
        'invoices',
        ['student_id', 'term_id', 'invoice_type', 'status'],
        unique=False,
    )
    
    # Composite index for debt queries:
    # WHERE student_id = ? AND status NOT IN (paid, cancelled, void)
    # Used in: get_outstanding_totals, dashboard debt aggregation
    op.create_index(
        'ix_invoices_student_status',
        'invoices',
        ['student_id', 'status'],
        unique=False,
    )
    
    # Date indexes for filtering by date ranges
    # Used in: accountant reports, dashboard revenue queries
    op.create_index(
        'ix_invoices_issue_date',
        'invoices',
        ['issue_date'],
        unique=False,
    )
    op.create_index(
        'ix_invoices_due_date',
        'invoices',
        ['due_date'],
        unique=False,
    )
    
    # === Payment indexes ===
    
    # Composite index for payment filtering:
    # WHERE student_id = ? AND status = ? AND payment_date BETWEEN ? AND ?
    # Used in: list_payments, accountant reports
    op.create_index(
        'ix_payments_student_status_date',
        'payments',
        ['student_id', 'status', 'payment_date'],
        unique=False,
    )
    
    # Date index for date range filtering
    # Used in: accountant reports, payment history
    op.create_index(
        'ix_payments_payment_date',
        'payments',
        ['payment_date'],
        unique=False,
    )
    
    # Index on reference for lookup (if used frequently)
    # Used in: payment search/filtering
    op.create_index(
        'ix_payments_reference',
        'payments',
        ['reference'],
        unique=False,
    )
    
    # === Credit Allocation indexes ===
    
    # Composite index for statement queries:
    # WHERE student_id = ? ORDER BY created_at DESC
    # Used in: student statement, balance history
    op.create_index(
        'ix_credit_allocations_student_created',
        'credit_allocations',
        ['student_id', 'created_at'],
        unique=False,
    )
    
    # === Invoice Line indexes ===
    
    # Index on kit_id for JOIN operations
    # Used in: generate_term_invoices (checking initial fees)
    op.create_index(
        'ix_invoice_lines_kit_id',
        'invoice_lines',
        ['kit_id'],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes in reverse order
    op.drop_index('ix_invoice_lines_kit_id', table_name='invoice_lines')
    op.drop_index('ix_credit_allocations_student_created', table_name='credit_allocations')
    op.drop_index('ix_payments_reference', table_name='payments')
    op.drop_index('ix_payments_payment_date', table_name='payments')
    op.drop_index('ix_payments_student_status_date', table_name='payments')
    op.drop_index('ix_invoices_due_date', table_name='invoices')
    op.drop_index('ix_invoices_issue_date', table_name='invoices')
    op.drop_index('ix_invoices_student_status', table_name='invoices')
    op.drop_index('ix_invoices_student_term_type_status', table_name='invoices')

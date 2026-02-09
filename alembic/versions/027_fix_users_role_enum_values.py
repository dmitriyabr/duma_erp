"""027 - Fix users.role enum values (PostgreSQL)

If the production DB was created with an ENUM type for users.role, adding new roles
later (e.g. Accountant) can make role updates fail at COMMIT time (500 in API).

This migration is safe on databases where users.role is not an ENUM (no-op).

Revision ID: 027
Revises: 026
Create Date: 2026-02-09
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # ALTER TYPE .. ADD VALUE may require autocommit depending on PG version/settings.
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute(
            """
DO $$
DECLARE
  role_nsp text;
  role_type text;
BEGIN
  SELECT n.nspname, t.typname
    INTO role_nsp, role_type
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_type t ON t.oid = a.atttypid
  WHERE c.relname = 'users'
    AND a.attname = 'role'
    AND a.attnum > 0
    AND NOT a.attisdropped
  LIMIT 1;

  IF role_type IS NULL THEN
    RETURN;
  END IF;

  -- Only proceed if the column type is an ENUM.
  IF EXISTS (SELECT 1 FROM pg_type t WHERE t.typname = role_type AND t.typtype = 'e') THEN
    IF NOT EXISTS (
      SELECT 1
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      WHERE t.typname = role_type AND e.enumlabel = 'SuperAdmin'
    ) THEN
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE %L', role_nsp, role_type, 'SuperAdmin');
    END IF;
    IF NOT EXISTS (
      SELECT 1
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      WHERE t.typname = role_type AND e.enumlabel = 'Admin'
    ) THEN
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE %L', role_nsp, role_type, 'Admin');
    END IF;
    IF NOT EXISTS (
      SELECT 1
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      WHERE t.typname = role_type AND e.enumlabel = 'User'
    ) THEN
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE %L', role_nsp, role_type, 'User');
    END IF;
    IF NOT EXISTS (
      SELECT 1
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      WHERE t.typname = role_type AND e.enumlabel = 'Accountant'
    ) THEN
      EXECUTE format('ALTER TYPE %I.%I ADD VALUE %L', role_nsp, role_type, 'Accountant');
    END IF;
  END IF;
END $$;
            """
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass


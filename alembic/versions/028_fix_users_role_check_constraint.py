"""028 - Fix users.role check constraint (PostgreSQL)

Some older/handmade schemas may have created users.role as a TEXT/VARCHAR column with a
CHECK constraint like:

    CHECK (role IN ('SuperAdmin','Admin','User'))

When a new role is introduced later (e.g. Accountant), updating a user's role can fail at
COMMIT time and bubble up as a 500 from the API.

This migration finds any CHECK constraints on users that appear to restrict the `role`
column and expands them to include the full set of roles used by the app.

Safe no-op when:
  - the DB is not PostgreSQL
  - there is no such CHECK constraint
  - the constraint already includes all roles

Revision ID: 028
Revises: 027
Create Date: 2026-02-09
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
DO $$
DECLARE
  users_nsp text;
  chk record;
  defn text;
BEGIN
  SELECT n.nspname
    INTO users_nsp
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relname = 'users'
    AND c.relkind = 'r'
  ORDER BY n.nspname
  LIMIT 1;

  IF users_nsp IS NULL THEN
    RETURN;
  END IF;

  FOR chk IN
    SELECT con.oid AS oid, con.conname AS conname
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'users'
      AND n.nspname = users_nsp
      AND con.contype = 'c'
  LOOP
    defn := pg_get_constraintdef(chk.oid);

    -- Heuristic: this constraint is about the role column and enumerates role labels.
    IF position('role' in defn) > 0
       AND (defn LIKE '%SuperAdmin%' OR defn LIKE '%Admin%' OR defn LIKE '%User%')
       AND defn NOT LIKE '%Accountant%'
    THEN
      EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', users_nsp, 'users', chk.conname);
      EXECUTE format(
        'ALTER TABLE %I.%I ADD CONSTRAINT %I CHECK (role IN (%L, %L, %L, %L))',
        users_nsp,
        'users',
        chk.conname,
        'SuperAdmin',
        'Admin',
        'User',
        'Accountant'
      );
    END IF;
  END LOOP;
END $$;
        """
    )


def downgrade() -> None:
    # No safe downgrade: we don't know the previous constraint definition.
    pass


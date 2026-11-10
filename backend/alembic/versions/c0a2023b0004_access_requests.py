"""access requests

Revision ID: c0a2023b0004
Revises: c0a2023b0003
Create Date: 2026-11-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0a2023b0004"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "access_requests"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("email"),
        sa.CheckConstraint("email = lower(email)"),
    )
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {TABLE} FROM PUBLIC")
    op.execute(
        f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON TABLE {TABLE} FROM anon';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON TABLE {TABLE} FROM authenticated';
              END IF;
            END
            $$
            """
    )


def downgrade() -> None:
    op.execute(
        f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'GRANT ALL ON TABLE {TABLE} TO anon';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'GRANT ALL ON TABLE {TABLE} TO authenticated';
              END IF;
            END
            $$
            """
    )
    op.execute(f"GRANT ALL ON TABLE {TABLE} TO PUBLIC")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY")
    op.drop_table(TABLE)

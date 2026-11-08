"""chunk page fields and default-deny RLS

Revision ID: c0a2023b0002
Revises: c0a2023b0001
Create Date: 2026-11-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0a2023b0002"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# v1 has no login. The Data API must not read the corpus.
# https://supabase.com/docs/guides/api/securing-your-api
# Grants decide which role can reach a table. RLS decides which rows.
# No grant and no policy means anon and authenticated see nothing.
# The direct database owner used by Alembic still bypasses RLS.
TABLES = ("source_documents", "cba_chunks")


def upgrade() -> None:
    op.add_column("cba_chunks", sa.Column("printed_page", sa.Integer(), nullable=True))
    op.add_column("cba_chunks", sa.Column("viewer_page", sa.Integer(), nullable=True))
    op.add_column("cba_chunks", sa.Column("quote_start", sa.Integer(), nullable=True))
    op.add_column("cba_chunks", sa.Column("quote_end", sa.Integer(), nullable=True))
    op.execute(
        """
        CREATE INDEX ix_cba_chunks_metadata_gin
        ON cba_chunks
        USING gin (chunk_metadata)
        """
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON TABLE {table} FROM anon';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON TABLE {table} FROM authenticated';
              END IF;
            END
            $$
            """
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'GRANT ALL ON TABLE {table} TO anon';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'GRANT ALL ON TABLE {table} TO authenticated';
              END IF;
            END
            $$
            """
        )
        op.execute(f"GRANT ALL ON TABLE {table} TO PUBLIC")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS ix_cba_chunks_metadata_gin")
    op.drop_column("cba_chunks", "quote_end")
    op.drop_column("cba_chunks", "quote_start")
    op.drop_column("cba_chunks", "viewer_page")
    op.drop_column("cba_chunks", "printed_page")

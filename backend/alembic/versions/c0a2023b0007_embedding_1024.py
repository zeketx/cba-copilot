"""resize chunk embeddings to 1024

Revision ID: c0a2023b0007
Revises: c0a2023b0006
Create Date: 2026-11-11

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c0a2023b0007"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = "ix_cba_chunks_embedding_hnsw"


def _resize(dimensions: int) -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
    op.execute("UPDATE cba_chunks SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute(
        "ALTER TABLE cba_chunks "
        f"ALTER COLUMN embedding TYPE vector({dimensions}) "
        f"USING NULL::vector({dimensions})"
    )
    op.execute(
        f"""
        CREATE INDEX {INDEX}
        ON cba_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def upgrade() -> None:
    _resize(1024)


def downgrade() -> None:
    _resize(1536)

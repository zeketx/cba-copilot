"""cba schema

Revision ID: c0a2023b0001
Revises:
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from app.database.constants import EMBEDDING_DIMENSIONS
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "c0a2023b0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("effective_start", sa.Text(), nullable=False),
        sa.Column("effective_through", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cba_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("article_number", sa.Integer(), nullable=True),
        sa.Column("article_title", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_cba_chunks_document_chunk"),
    )
    op.create_index("ix_cba_chunks_document_id", "cba_chunks", ["document_id"])
    op.create_index("ix_cba_chunks_article", "cba_chunks", ["article_number"])
    op.execute(
        """
        ALTER TABLE cba_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'english',
                coalesce(article_title, '') || ' ' || coalesce(section, '') || ' ' || text
            )
        ) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_cba_chunks_embedding_hnsw
        ON cba_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_cba_chunks_search_vector_gin
        ON cba_chunks
        USING gin (search_vector)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cba_chunks_search_vector_gin")
    op.execute("DROP INDEX IF EXISTS ix_cba_chunks_embedding_hnsw")
    op.drop_index("ix_cba_chunks_article", table_name="cba_chunks")
    op.drop_index("ix_cba_chunks_document_id", table_name="cba_chunks")
    op.drop_table("cba_chunks")
    op.drop_table("source_documents")

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.constants import EMBEDDING_DIMENSIONS


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    effective_start: Mapped[str] = mapped_column(Text, nullable=False)
    effective_through: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list[CbaChunk]] = relationship(back_populates="document")


class CbaChunk(Base):
    __tablename__ = "cba_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_cba_chunks_document_chunk"),
        Index("ix_cba_chunks_document_id", "document_id"),
        Index("ix_cba_chunks_article", "article_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    article_number: Mapped[int | None] = mapped_column(Integer)
    article_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    section: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    token_count: Mapped[int | None] = mapped_column(Integer)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(article_title, '') || ' ' || "
            "coalesce(section, '') || ' ' || text)",
            persisted=True,
        ),
    )
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[SourceDocument] = relationship(back_populates="chunks")

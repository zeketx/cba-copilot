from __future__ import annotations

import uuid
from typing import Any

from app.database.models import CbaChunk, SourceDocument
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ingest.rows import ChunkRow


def document_upsert_statement(
    *,
    title: str,
    source_url: str,
    sha256: str,
    cover_date: str,
    printed_term: str,
    page_offset: int,
    effective_start: str,
    effective_through: str,
    text: str,
):
    table = SourceDocument.__table__
    stmt = pg_insert(table).values(
        id=uuid.uuid4(),
        title=title,
        source_url=source_url,
        sha256=sha256,
        cover_date=cover_date,
        printed_term=printed_term,
        page_offset=page_offset,
        effective_start=effective_start,
        effective_through=effective_through,
        text=text,
    )
    excluded = stmt.excluded
    return stmt.on_conflict_do_update(
        index_elements=["source_url"],
        set_={
            "title": excluded.title,
            "sha256": excluded.sha256,
            "cover_date": excluded.cover_date,
            "printed_term": excluded.printed_term,
            "page_offset": excluded.page_offset,
            "effective_start": excluded.effective_start,
            "effective_through": excluded.effective_through,
            "text": excluded.text,
            "updated_at": func.now(),
        },
    ).returning(table.c.id)


def chunk_upsert_statement(document_id: uuid.UUID, rows: list[ChunkRow]):
    table = CbaChunk.__table__
    values = [_chunk_values(document_id, row) for row in rows]
    stmt = pg_insert(table).values(values)
    excluded = stmt.excluded
    return stmt.on_conflict_do_update(
        index_elements=["document_id", "chunk_index"],
        set_={
            "article_number": excluded.article_number,
            "article_title": excluded.article_title,
            "section": excluded.section,
            "page_start": excluded.page_start,
            "page_end": excluded.page_end,
            "printed_page": excluded.printed_page,
            "viewer_page": excluded.viewer_page,
            "source_url": excluded.source_url,
            "text": excluded.text,
            "chunk_metadata": excluded.chunk_metadata,
            "embedding": case(
                (table.c.text.is_distinct_from(excluded.text), None),
                else_=table.c.embedding,
            ),
        },
    )


def upsert_document(conn: Connection, **fields: Any) -> uuid.UUID:
    document_id = conn.execute(document_upsert_statement(**fields)).scalar_one()
    return document_id


def stale_chunks_delete(document_id: uuid.UUID, keep: int):
    return delete(CbaChunk).where(
        CbaChunk.document_id == document_id,
        CbaChunk.chunk_index >= keep,
    )


def upsert_chunks(conn: Connection, document_id: uuid.UUID, rows: list[ChunkRow]) -> None:
    if rows:
        conn.execute(chunk_upsert_statement(document_id, rows))
    conn.execute(stale_chunks_delete(document_id, len(rows)))


def embed_missing(
    conn: Connection,
    document_id: uuid.UUID,
    embedder: Any,
    batch_size: int = 96,
) -> int:
    batch = conn.execute(
        select(CbaChunk.id, CbaChunk.text)
        .where(CbaChunk.document_id == document_id, CbaChunk.embedding.is_(None))
        .order_by(CbaChunk.chunk_index)
        .limit(batch_size)
    ).all()
    if not batch:
        return 0
    vectors = embedder.embed_documents([row.text for row in batch])
    for row, vector in zip(batch, vectors, strict=True):
        conn.execute(update(CbaChunk).where(CbaChunk.id == row.id).values(embedding=vector))
    return len(batch)


def _chunk_values(document_id: uuid.UUID, row: ChunkRow) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "document_id": document_id,
        "chunk_index": row.chunk_index,
        "article_number": row.article_number,
        "article_title": row.article_title,
        "section": row.section,
        "page_start": row.page_start,
        "page_end": row.page_end,
        "printed_page": row.printed_page,
        "viewer_page": row.viewer_page,
        "source_url": row.source_url,
        "text": row.text,
        "chunk_metadata": row.metadata,
    }

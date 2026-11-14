from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain import Chunk
from app.retrieval.queries import (
    chunk_by_id_sql,
    chunks_by_ids_sql,
    context_batch_sql,
    keyword_search_sql,
    neighbor_batch_sql,
    vector_search_sql,
)
from app.retrieval.text import tokens
from app.retrieval.types import DocumentMeta, LoadedContext


class ChunkStore(Protocol):
    def vector_search(self, vector: list[float], limit: int) -> list[str]: ...

    def keyword_search(self, query: str, limit: int) -> list[str]: ...

    def get(self, passage_id: str) -> Chunk | None: ...

    def get_many(self, passage_ids: list[str]) -> dict[str, Chunk]: ...

    def load_context(self, hits: list[Chunk], articles: list[int]) -> LoadedContext: ...

def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))

def _source_base(url: str) -> str:
    return url.split("#", 1)[0]

def documents_for(documents: list[DocumentMeta], passages: list[Chunk]) -> list[DocumentMeta]:
    bases = {_source_base(passage.source_url) for passage in passages}
    found: list[DocumentMeta] = []
    seen: set[str] = set()
    for document in documents:
        if document.id in seen:
            continue
        if _source_base(document.source_url) in bases:
            seen.add(document.id)
            found.append(document)
    return found

def _memory_neighbors(
    chunks: dict[str, Chunk],
    order: list[str],
    passage_id: str,
) -> tuple[str | None, str | None]:
    chunk = chunks.get(passage_id)
    if chunk is None:
        return None, None
    same = [
        item_id
        for item_id in order
        if chunks[item_id].article_number == chunk.article_number
    ]
    index = same.index(passage_id)
    prev_id = same[index - 1] if index else None
    next_id = same[index + 1] if index + 1 < len(same) else None
    return prev_id, next_id

class MemoryChunkStore:
    def __init__(
        self,
        chunks: list[Chunk],
        vectors: dict[str, list[float]] | None = None,
        *,
        documents: list[DocumentMeta] | None = None,
    ) -> None:
        self._chunks = {chunk.id: chunk for chunk in chunks}
        self._order = [chunk.id for chunk in chunks]
        self._vectors = vectors or {}
        self._documents = list(documents or [])

    def vector_search(self, vector: list[float], limit: int) -> list[str]:
        scored: list[tuple[float, str]] = []
        for passage_id in self._order:
            stored = self._vectors.get(passage_id)
            if stored is None:
                continue
            score = _cosine(vector, stored)
            if score > 0:
                scored.append((score, passage_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [passage_id for _, passage_id in scored[:limit]]

    def keyword_search(self, query: str, limit: int) -> list[str]:
        query_tokens = tokens(query)
        scored: list[tuple[int, str]] = []
        for passage_id in self._order:
            chunk = self._chunks[passage_id]
            haystack = tokens(f"{chunk.text} {chunk.section} {chunk.article_title}")
            overlap = len(query_tokens & haystack)
            if overlap:
                scored.append((overlap, passage_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [passage_id for _, passage_id in scored[:limit]]

    def get(self, passage_id: str) -> Chunk | None:
        return self._chunks.get(passage_id)

    def get_many(self, passage_ids: list[str]) -> dict[str, Chunk]:
        return {
            passage_id: self._chunks[passage_id]
            for passage_id in passage_ids
            if passage_id in self._chunks
        }

    def load_context(self, hits: list[Chunk], articles: list[int]) -> LoadedContext:
        if not hits:
            return LoadedContext()
        neighbors: dict[str, tuple[Chunk | None, Chunk | None]] = {}
        for hit in hits:
            prev_id, next_id = _memory_neighbors(self._chunks, self._order, hit.id)
            neighbors[hit.id] = (
            self.get(prev_id) if prev_id else None,
            self.get(next_id) if next_id else None,
        )
        wanted = set(articles)
        grouped: dict[int, list[Chunk]] = {article: [] for article in articles}
        for passage_id in self._order:
            chunk = self._chunks[passage_id]
            if chunk.article_number in wanted:
                grouped[chunk.article_number].append(chunk)
        return LoadedContext(neighbors=neighbors, articles=grouped, documents=list(self._documents))

def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"

def _chunk_from_row(row: object) -> Chunk:
    body = getattr(row, "body", None)
    if body is None:
        body = row.text
    return Chunk(
        id=str(row.id),
        article_number=row.article_number,
        article_title=row.article_title or "",
        section=row.section or "",
        page_start=row.page_start,
        page_end=row.page_end,
        text=body or "",
        source_url=row.source_url or "",
    )

def _document_from_row(row: object) -> DocumentMeta:
    return DocumentMeta(
        id=str(row.id),
        title=row.title or "",
        source_url=row.source_url or "",
        sha256=row.sha256,
        cover_date=row.cover_date,
        printed_term=row.printed_term,
        page_offset=row.page_offset,
        effective_start=row.effective_start or "",
        effective_through=row.effective_through or "",
    )

def postgres_session_factory(database_url: str) -> Callable[[], Session]:
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)


class PostgresChunkStore:

    def __init__(self, session: Session, chunks_by_id: dict[str, Chunk] | None = None) -> None:
        self._session = session
        self._chunks = chunks_by_id or {}

    def vector_search(self, vector: list[float], limit: int) -> list[str]:
        rows = self._session.execute(
            text(vector_search_sql()),
            {"query_vec": _vector_literal(vector), "limit": limit},
        ).all()
        return [str(row.id) for row in rows]

    def keyword_search(self, query: str, limit: int) -> list[str]:
        rows = self._session.execute(
            text(keyword_search_sql()),
            {"query_text": query, "limit": limit},
        ).all()
        return [str(row.id) for row in rows]

    def get(self, passage_id: str) -> Chunk | None:
        cached = self._chunks.get(passage_id)
        if cached is not None:
            return cached
        row = self._session.execute(
            text(chunk_by_id_sql()),
            {"chunk_id": passage_id},
        ).first()
        if row is None:
            return None
        chunk = _chunk_from_row(row)
        self._chunks[passage_id] = chunk
        return chunk

    def get_many(self, passage_ids: list[str]) -> dict[str, Chunk]:
        found: dict[str, Chunk] = {}
        missing: list[str] = []
        seen: set[str] = set()
        for passage_id in passage_ids:
            if passage_id in seen:
                continue
            seen.add(passage_id)
            cached = self._chunks.get(passage_id)
            if cached is not None:
                found[passage_id] = cached
            else:
                missing.append(passage_id)
        if not missing:
            return found
        rows = self._session.execute(
            text(chunks_by_ids_sql()),
            {"chunk_ids": ",".join(missing)},
        ).all()
        for row in rows:
            chunk = _chunk_from_row(row)
            self._chunks[chunk.id] = chunk
            found[chunk.id] = chunk
        return found

    def load_context(self, hits: list[Chunk], articles: list[int]) -> LoadedContext:
        if not hits:
            return LoadedContext()
        hit_ids = ",".join(hit.id for hit in hits)
        article_ids = ",".join(str(article) for article in articles)
        neighbor_rows = self._session.execute(
            text(neighbor_batch_sql()),
            {"hit_ids": hit_ids},
        ).all()
        context_rows = self._session.execute(
            text(context_batch_sql()),
            {"hit_ids": hit_ids, "articles": article_ids},
        ).all()
        neighbors: dict[str, list[Chunk | None]] = {hit.id: [None, None] for hit in hits}
        for row in neighbor_rows:
            chunk = _chunk_from_row(row)
            self._chunks[chunk.id] = chunk
            pair = neighbors.setdefault(str(row.hit_id), [None, None])
            if row.slot == "prev":
                pair[0] = chunk
            elif row.slot == "next":
                pair[1] = chunk
        grouped: dict[int, list[Chunk]] = {article: [] for article in articles}
        documents: list[DocumentMeta] = []
        seen_docs: set[str] = set()
        for row in context_rows:
            if row.kind == "chunk":
                chunk = _chunk_from_row(row)
                self._chunks[chunk.id] = chunk
                if chunk.article_number in grouped:
                    grouped[chunk.article_number].append(chunk)
                continue
            if row.kind != "document":
                continue
            document = _document_from_row(row)
            if document.id in seen_docs:
                continue
            seen_docs.add(document.id)
            documents.append(document)
        return LoadedContext(
            neighbors={hit_id: (pair[0], pair[1]) for hit_id, pair in neighbors.items()},
            articles=grouped,
            documents=documents,
        )

from __future__ import annotations

from typing import Protocol

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.domain import Chunk
from app.retrieval.queries import (
    chunk_by_id_sql,
    keyword_search_sql,
    neighbor_sql,
    section_candidates_sql,
    source_documents_sql,
    vector_search_sql,
)
from app.retrieval.refs import select_section_ids
from app.retrieval.text import tokens
from app.retrieval.types import DocumentMeta


class ChunkStore(Protocol):
    def vector_search(self, vector: list[float], limit: int) -> list[str]: ...

    def keyword_search(self, query: str, limit: int) -> list[str]: ...

    def get(self, passage_id: str) -> Chunk | None: ...

    def neighbor_ids(self, passage_id: str) -> tuple[str | None, str | None]: ...

    def section_ids(self, article_number: int, section: str) -> list[str]: ...

    def source_documents(self, passage_ids: list[str]) -> list[DocumentMeta]: ...

def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))

def _source_base(url: str) -> str:
    return url.split("#", 1)[0]

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

    def neighbor_ids(self, passage_id: str) -> tuple[str | None, str | None]:
        chunk = self._chunks.get(passage_id)
        if chunk is None:
            return None, None
        same = [
            item_id
            for item_id in self._order
            if self._chunks[item_id].article_number == chunk.article_number
        ]
        index = same.index(passage_id)
        prev_id = same[index - 1] if index else None
        next_id = same[index + 1] if index + 1 < len(same) else None
        return prev_id, next_id

    def section_ids(self, article_number: int, section: str) -> list[str]:
        rows = [
            (passage_id, self._chunks[passage_id].section)
            for passage_id in self._order
            if self._chunks[passage_id].article_number == article_number
        ]
        return select_section_ids(rows, section)

    def source_documents(self, passage_ids: list[str]) -> list[DocumentMeta]:
        bases: set[str] = set()
        for passage_id in passage_ids:
            chunk = self._chunks.get(passage_id)
            if chunk is not None:
                bases.add(_source_base(chunk.source_url))
        found: list[DocumentMeta] = []
        seen: set[str] = set()
        for document in self._documents:
            if document.id in seen:
                continue
            if _source_base(document.source_url) in bases:
                seen.add(document.id)
                found.append(document)
        return found

def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"

def _chunk_from_row(row: object) -> Chunk:
    return Chunk(
        id=str(row.id),
        article_number=row.article_number,
        article_title=row.article_title or "",
        section=row.section or "",
        page_start=row.page_start,
        page_end=row.page_end,
        text=row.text,
        source_url=row.source_url,
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

    def neighbor_ids(self, passage_id: str) -> tuple[str | None, str | None]:
        rows = self._session.execute(
            text(neighbor_sql()),
            {"chunk_id": passage_id},
        ).all()
        prev_id = None
        next_id = None
        for row in rows:
            if row.slot == "prev":
                prev_id = str(row.id)
            elif row.slot == "next":
                next_id = str(row.id)
        return prev_id, next_id

    def section_ids(self, article_number: int, section: str) -> list[str]:
        rows = self._session.execute(
            text(section_candidates_sql()),
            {"article": article_number},
        ).all()
        pairs = [(str(row.id), str(row.section or "")) for row in rows]
        return select_section_ids(pairs, section)

    def source_documents(self, passage_ids: list[str]) -> list[DocumentMeta]:
        if not passage_ids:
            return []
        statement = text(source_documents_sql()).bindparams(
            bindparam("chunk_ids", expanding=True)
        )
        rows = self._session.execute(statement, {"chunk_ids": passage_ids}).all()
        return [_document_from_row(row) for row in rows]

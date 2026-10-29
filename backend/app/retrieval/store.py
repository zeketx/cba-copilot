
from __future__ import annotations

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain import Chunk
from app.retrieval.queries import keyword_search_sql, vector_search_sql
from app.retrieval.text import tokens


class ChunkStore(Protocol):
    def vector_search(self, vector: list[float], limit: int) -> list[str]: ...

    def keyword_search(self, query: str, limit: int) -> list[str]: ...

    def get(self, passage_id: str) -> Chunk | None: ...

def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))

class MemoryChunkStore:
    def __init__(self, chunks: list[Chunk], vectors: dict[str, list[float]] | None = None) -> None:
        self._chunks = {chunk.id: chunk for chunk in chunks}
        self._order = [chunk.id for chunk in chunks]
        self._vectors = vectors or {}

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

def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"

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
        return self._chunks.get(passage_id)

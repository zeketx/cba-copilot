from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pgvector import Vector as PgVector
from pgvector.psycopg import register_vector
from sqlalchemy import bindparam, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import UserDefinedType

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

_NAMED_BIND = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


class NativeVector(UserDefinedType):
    """Bind a pgvector.Vector so psycopg uses the binary dumper.

    pgvector.sqlalchemy.VECTOR.bind_processor stringifies through Vector._to_db.
    SQLAlchemy then sends text, Postgres parses 1024 floats, and HNSW timing
    stays in the hundreds of milliseconds instead of the typed-constant 35 ms.
    """

    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        del kw
        return "vector"

    def bind_processor(self, dialect):
        del dialect

        def process(value):
            if value is None:
                return None
            if isinstance(value, PgVector):
                return value
            return PgVector(value)

        return process


@dataclass
class QueryProbe:
    sql: str
    path: str = "sqlalchemy"
    param_python_type: str = ""
    param_dbapi_type: str = ""
    acquire_ms: float = 0.0
    encode_ms: float = 0.0
    execute_ms: float = 0.0
    fetch_ms: float = 0.0


class ChunkStore(Protocol):
    def vector_search(self, vector: list[float], limit: int) -> list[str]: ...

    def keyword_search(self, query: str, limit: int) -> list[str]: ...

    def get(self, passage_id: str) -> Chunk | None: ...

    def get_many(self, passage_ids: list[str]) -> dict[str, Chunk]: ...

    def load_context(
        self,
        hits: list[Chunk],
        articles: list[int],
        sections: list[str] | None = None,
    ) -> LoadedContext: ...


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


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def driver_sql(sql: str) -> str:
    """Turn SQLAlchemy :name binds into psycopg %(name)s, leaving ::casts alone.

    psycopg treats % as a placeholder marker. Literal percents (ILIKE
    wildcards such as `'%' || needle || '%'`) must be %% on the driver
    path. Double them before rewriting :name so %(name)s is not escaped.
    """
    return _NAMED_BIND.sub(r"%(\1)s", sql.replace("%", "%%"))


def as_pgvector(value: object) -> PgVector:
    if isinstance(value, PgVector):
        return value
    if isinstance(value, list):
        return PgVector(value)
    raise TypeError(f"query_vec must be list[float] or Vector, got {type(value).__name__}")


def _psycopg_connection(session: Session):
    try:
        sa_conn = session.connection()
    except Exception:
        return None
    pool_proxied = getattr(sa_conn, "connection", None)
    dbapi = getattr(pool_proxied, "dbapi_connection", None)
    if dbapi is None:
        dbapi = getattr(pool_proxied, "driver_connection", None)
    if dbapi is None:
        dbapi = pool_proxied
    module = type(dbapi).__module__
    if not str(module).startswith("psycopg"):
        return None
    return dbapi


def _vector_dumper_name(raw, value: object) -> str:
    if value is None:
        return ""
    try:
        from psycopg.adapt import PyFormat

        dumper = raw.adapters.get_dumper(type(value), PyFormat.BINARY)
        kind = "binary"
        if dumper is None:
            dumper = raw.adapters.get_dumper(type(value), PyFormat.TEXT)
            kind = "text"
        if dumper is None:
            return "unregistered"
        return f"{type(dumper).__name__}/{kind}"
    except Exception:
        return "unknown"


def _namedtuple_row():
    from psycopg.rows import namedtuple_row

    return namedtuple_row


def _execute_probed(
    session: Session,
    sql: str,
    params: dict[str, object],
    *,
    vector_key: str | None = None,
) -> tuple[list[object], QueryProbe]:
    probe = QueryProbe(sql=sql)
    encoded: dict[str, object] = dict(params)
    started = time.perf_counter()
    if vector_key and encoded.get(vector_key) is not None:
        encoded[vector_key] = as_pgvector(encoded[vector_key])
    probe.encode_ms = _elapsed_ms(started)
    if vector_key and vector_key in encoded and encoded[vector_key] is not None:
        value = encoded[vector_key]
        probe.param_python_type = f"{type(value).__module__}.{type(value).__name__}"

    started = time.perf_counter()
    raw = _psycopg_connection(session)
    probe.acquire_ms = _elapsed_ms(started)
    if raw is not None:
        probe.path = "psycopg"
        if vector_key:
            probe.param_dbapi_type = _vector_dumper_name(raw, encoded.get(vector_key))
        started = time.perf_counter()
        with raw.cursor(row_factory=_namedtuple_row()) as cur:
            cur.execute(driver_sql(sql), encoded)
            probe.execute_ms = _elapsed_ms(started)
            started = time.perf_counter()
            rows = list(cur.fetchall())
            probe.fetch_ms = _elapsed_ms(started)
        return rows, probe

    probe.path = "sqlalchemy"
    statement = text(sql)
    if vector_key:
        statement = statement.bindparams(bindparam(vector_key, type_=NativeVector()))
        if encoded.get(vector_key) is not None:
            probe.param_dbapi_type = type(encoded[vector_key]).__name__
    started = time.perf_counter()
    result = session.execute(statement, encoded)
    probe.execute_ms = _elapsed_ms(started)
    started = time.perf_counter()
    rows = list(result.all())
    probe.fetch_ms = _elapsed_ms(started)
    return rows, probe


def _row_id(row: object) -> str:
    if hasattr(row, "id"):
        return str(row.id)
    return str(row[0])  # type: ignore[index]


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

    def load_context(
        self,
        hits: list[Chunk],
        articles: list[int],
        sections: list[str] | None = None,
    ) -> LoadedContext:
        del sections
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


def _chunk_from_row(row: object) -> Chunk:
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        raw = mapping["body"] if "body" in mapping else mapping.get("text")
    elif hasattr(row, "body"):
        raw = row.body
    else:
        raw = getattr(row, "text", None)
    return Chunk(
        id=str(row.id),
        article_number=row.article_number,
        article_title=row.article_title or "",
        section=row.section or "",
        page_start=row.page_start,
        page_end=row.page_end,
        text=raw or "",
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
    engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _register_pgvector(dbapi_connection, _connection_record) -> None:
        register_vector(dbapi_connection)
        # Direct session host only (Settings rejects pooler.supabase.com).
        # Prepare on first execute so a transaction-mode pooler cannot hide a
        # per-call PARSE inside vector_ms. Session-mode connections reuse it.
        if hasattr(dbapi_connection, "prepare_threshold"):
            dbapi_connection.prepare_threshold = 0

    return sessionmaker(bind=engine)


class PostgresChunkStore:

    def __init__(self, session: Session, chunks_by_id: dict[str, Chunk] | None = None) -> None:
        self._session = session
        self._chunks = chunks_by_id or {}
        self._vector_probe: QueryProbe | None = None
        self._neighbor_probe: QueryProbe | None = None
        self._context_probe: QueryProbe | None = None

    def vector_search(self, vector: list[float], limit: int) -> list[str]:
        rows, probe = _execute_probed(
            self._session,
            vector_search_sql(),
            {"query_vec": vector, "limit": limit},
            vector_key="query_vec",
        )
        self._vector_probe = probe
        return [_row_id(row) for row in rows]

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

    def load_context(
        self,
        hits: list[Chunk],
        articles: list[int],
        sections: list[str] | None = None,
    ) -> LoadedContext:
        if not hits:
            return LoadedContext()
        hit_ids = ",".join(hit.id for hit in hits)
        article_ids = ",".join(str(article) for article in articles)
        section_needles = "|||".join(sections or [])
        neighbor_rows, neighbor_probe = _execute_probed(
            self._session,
            neighbor_batch_sql(),
            {"hit_ids": hit_ids},
        )
        self._neighbor_probe = neighbor_probe
        context_rows, context_probe = _execute_probed(
            self._session,
            context_batch_sql(),
            {
                "hit_ids": hit_ids,
                "articles": article_ids,
                "sections": section_needles,
            },
        )
        self._context_probe = context_probe
        neighbors: dict[str, list[Chunk | None]] = {hit.id: [None, None] for hit in hits}
        for row in neighbor_rows:
            chunk = _chunk_from_row(row)
            if chunk.text:
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
                if chunk.text:
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

    def last_query_timings(self) -> dict[str, float]:
        out: dict[str, float] = {}
        if self._vector_probe is not None:
            out["vector_acquire_ms"] = self._vector_probe.acquire_ms
            out["vector_encode_ms"] = self._vector_probe.encode_ms
            out["vector_execute_ms"] = self._vector_probe.execute_ms
            out["vector_fetch_ms"] = self._vector_probe.fetch_ms
        if self._neighbor_probe is not None:
            out["context_neighbor_acquire_ms"] = self._neighbor_probe.acquire_ms
            out["context_neighbor_execute_ms"] = self._neighbor_probe.execute_ms
            out["context_neighbor_fetch_ms"] = self._neighbor_probe.fetch_ms
        if self._context_probe is not None:
            out["context_label_acquire_ms"] = self._context_probe.acquire_ms
            out["context_label_execute_ms"] = self._context_probe.execute_ms
            out["context_label_fetch_ms"] = self._context_probe.fetch_ms
        return out

    def query_path_evidence(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self._vector_probe is not None:
            probe = self._vector_probe
            out["vector_sql"] = probe.sql
            out["vector_path"] = probe.path
            out["vector_param_python_type"] = probe.param_python_type
            out["vector_param_dbapi_type"] = probe.param_dbapi_type
            out["vector_acquire_ms"] = f"{probe.acquire_ms:.3f}"
            out["vector_encode_ms"] = f"{probe.encode_ms:.3f}"
            out["vector_execute_ms"] = f"{probe.execute_ms:.3f}"
            out["vector_fetch_ms"] = f"{probe.fetch_ms:.3f}"
        if self._neighbor_probe is not None:
            probe = self._neighbor_probe
            out["neighbor_sql"] = probe.sql
            out["neighbor_path"] = probe.path
            out["neighbor_execute_ms"] = f"{probe.execute_ms:.3f}"
            out["neighbor_fetch_ms"] = f"{probe.fetch_ms:.3f}"
        if self._context_probe is not None:
            probe = self._context_probe
            out["context_sql"] = probe.sql
            out["context_path"] = probe.path
            out["context_execute_ms"] = f"{probe.execute_ms:.3f}"
            out["context_fetch_ms"] = f"{probe.fetch_ms:.3f}"
        return out

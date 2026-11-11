from types import SimpleNamespace

import pytest
from app.corpus import pdf_url
from app.demo import demo_embedder, demo_store
from app.domain import Chunk, Claim, DraftAnswer
from app.grounding.validate import validate_draft
from app.pipeline import answer_question
from app.retrieval.embed import HashEmbedder
from app.retrieval.hybrid import evidence_is_adequate, hybrid_retrieve
from app.retrieval.queries import (
    chunk_by_id_sql,
    keyword_search_sql,
    neighbor_sql,
    section_candidates_sql,
    source_documents_sql,
    vector_search_sql,
)
from app.retrieval.store import MemoryChunkStore, PostgresChunkStore
from app.retrieval.types import DocumentMeta


def _chunk(
    chunk_id: str,
    text: str,
    section: str = "1",
    *,
    article: int | None = 7,
) -> Chunk:
    return Chunk(
        id=chunk_id,
        article_number=article,
        article_title="Salary Cap",
        section=section,
        page_start=1,
        page_end=1,
        text=text,
        source_url="https://example.test/cba.pdf#page=1",
    )


def _memory(
    chunks: list[Chunk],
    *,
    vectors: dict[str, list[float]] | None = None,
    documents: list[DocumentMeta] | None = None,
) -> tuple[HashEmbedder, MemoryChunkStore]:
    embedder = HashEmbedder(dimensions=64)
    stored = vectors
    if stored is None:
        stored = {chunk.id: embedder.embed_query(chunk.text) for chunk in chunks}
    return embedder, MemoryChunkStore(chunks, stored, documents=documents)


def test_sql_uses_vector_and_full_text() -> None:
    vector_sql = vector_search_sql()
    keyword_sql = keyword_search_sql()
    assert "<=>" in vector_sql
    assert "vector" in vector_sql
    assert "search_vector" in keyword_sql
    assert "plainto_tsquery" in keyword_sql
    assert "@@" in keyword_sql


def test_hybrid_fuses_memory_hits() -> None:
    apron = _chunk(
        "apron",
        "Second Apron Level trade aggregation cash",
        "2(e) Transaction Restrictions",
    )
    other = _chunk("other", "Hotel incidentals and parking stalls", "1 Hotel")
    embedder = HashEmbedder(dimensions=64)
    store = MemoryChunkStore(
        [apron, other],
        {
            apron.id: embedder.embed_query(apron.text),
            other.id: embedder.embed_query(other.text),
        },
    )
    result = hybrid_retrieve(store, "second apron trade", embedder, top_k=2, candidate_k=5)
    assert result.hits[0].id == "apron"
    assert evidence_is_adequate("second apron trade", result.hits)
    assert not evidence_is_adequate("nhl coach timeouts overtime", result.hits)


def test_neighbors_stay_inside_the_article_and_follow_chunk_order() -> None:
    late = _chunk("late", "isolated late section", "10 Late")
    middle = _chunk("middle", "purple marquee middle section", "2 Middle")
    other = _chunk("other", "isolated other article", "1 Other", article=8)
    nxt = _chunk("next", "isolated following section", "2 Next", article=8)
    embedder, store = _memory([late, middle, other, nxt])
    middle_hit = hybrid_retrieve(
        store,
        "purple marquee middle",
        embedder,
        top_k=1,
        candidate_k=5,
    )
    assert [hit.id for hit in middle_hit.hits] == ["middle"]
    assert [chunk.id for chunk in middle_hit.context] == ["late"]
    other_hit = hybrid_retrieve(
        store,
        "isolated other article",
        embedder,
        top_k=1,
        candidate_k=5,
    )
    assert [hit.id for hit in other_hit.hits] == ["other"]
    assert [chunk.id for chunk in other_hit.context] == ["next"]


def test_cross_reference_resolves_the_named_section() -> None:
    query = "unique lookup phrase"
    hit = _chunk(
        "hit",
        f"{query}. See Section 6(j) of this Article. Article VII, Section 2(e) applies.",
        "1 Intro",
    )
    exact = _chunk(
        "exact-j",
        "traded exception body",
        "6. Exceptions to the Salary Cap / (j) Traded",
    )
    child = _chunk(
        "child-j",
        "deeper child body",
        "6. Exceptions to the Salary Cap / (j)(1)(i) Standard",
    )
    target = _chunk("target-e", "restrictions body", "2(e) Transaction Restrictions")
    decoy = _chunk(
        "decoy-e",
        "other article restrictions",
        "2(e) Transaction Restrictions",
        article=8,
    )
    embedder = HashEmbedder(dimensions=64)
    vectors = {
        chunk.id: embedder.embed_query(chunk.text)
        for chunk in (exact, child, target, decoy)
    }
    vectors["hit"] = embedder.embed_query(query)
    store = MemoryChunkStore([hit, exact, child, target, decoy], vectors)
    result = hybrid_retrieve(store, query, embedder, top_k=1, candidate_k=5)
    assert [item.id for item in result.hits] == ["hit"]
    assert [item.id for item in result.context] == ["exact-j", "target-e"]


def test_cross_reference_uses_a_child_when_the_section_is_missing() -> None:
    query = "orphan parent phrase"
    hit = _chunk("hit-child", f"{query}. See Section 6(j) of this Article.", "1 Intro")
    spacer = _chunk("spacer", "spacer body", "2 Spacer")
    child = _chunk("child-only", "only child text", "6(j)(1) Child")
    embedder = HashEmbedder(dimensions=64)
    zero = [0.0] * embedder.dimensions
    store = MemoryChunkStore(
        [hit, spacer, child],
        {
            "hit-child": embedder.embed_query(query),
            "spacer": zero,
            "child-only": zero,
        },
    )
    result = hybrid_retrieve(store, query, embedder, top_k=1, candidate_k=5)
    assert [item.id for item in result.context] == ["spacer", "child-only"]


def test_unresolvable_cross_reference_is_skipped() -> None:
    query = "lonely phrase"
    hit = _chunk(
        "lonely",
        f"{query}. See Section 99(z) of this Article. Article XXXIX controls.",
        "1 Intro",
    )
    neighbor = _chunk("neighbor", "quiet hallway", "2 Hallway")
    embedder = HashEmbedder(dimensions=64)
    store = MemoryChunkStore(
        [hit, neighbor],
        {
            "lonely": embedder.embed_query(query),
            "neighbor": embedder.embed_query(neighbor.text),
        },
    )
    result = hybrid_retrieve(store, query, embedder, top_k=1, candidate_k=5)
    assert [item.id for item in result.context] == ["neighbor"]


def test_context_dedupes_hits_and_repeated_targets() -> None:
    query = "shared salary cap restriction"
    first = _chunk(
        "first",
        f"{query}. See Section 3 of this Article.",
        "1 First",
    )
    second = _chunk("second", query, "2 Second")
    tail = _chunk("tail", "unrelated hotel parking", "3 Tail")
    embedder = HashEmbedder(dimensions=64)
    zero = [0.0] * embedder.dimensions
    query_vector = embedder.embed_query(query)
    store = MemoryChunkStore(
        [first, second, tail],
        {"first": query_vector, "second": query_vector, "tail": zero},
    )
    result = hybrid_retrieve(store, query, embedder, top_k=2, candidate_k=5)
    assert [item.id for item in result.hits] == ["first", "second"]
    assert [item.id for item in result.context] == ["tail"]


def test_context_caps_keep_hit_rank_and_stop() -> None:
    query = "zebra quota salary"
    embedder = HashEmbedder(dimensions=64)
    previous = _chunk("n1", "prelude isolated", "1 Prelude")
    primary = _chunk(
        "h1",
        f"{query}. See Section 8 of this Article.",
        "2 Primary",
    )
    following = _chunk("follow", "following isolated", "3 Following")
    cited = _chunk("cited", "cited section body", "8 Cited")
    secondary_prev = _chunk("n2", "other prelude isolated", "1 Other", article=8)
    secondary = _chunk("h2", "zebra only", "2 Secondary", article=8)
    chunks = [previous, primary, following, cited, secondary_prev, secondary]
    vectors = {chunk.id: [0.0] * embedder.dimensions for chunk in chunks}
    vectors["h1"] = embedder.embed_query(query)
    vectors["h2"] = embedder.embed_query("zebra")
    store = MemoryChunkStore(chunks, vectors)
    capped = hybrid_retrieve(
        store,
        query,
        embedder,
        top_k=2,
        candidate_k=6,
        context_per_hit=4,
        context_max=1,
    )
    assert [item.id for item in capped.hits] == ["h1", "h2"]
    assert [item.id for item in capped.context] == ["n1"]
    per_hit = hybrid_retrieve(
        store,
        query,
        embedder,
        top_k=1,
        candidate_k=6,
        context_per_hit=1,
        context_max=16,
    )
    assert [item.id for item in per_hit.hits] == ["h1"]
    assert [item.id for item in per_hit.context] == ["n1"]


def test_negative_context_cap_is_rejected() -> None:
    embedder, store = _memory([])
    with pytest.raises(ValueError):
        hybrid_retrieve(store, "apron", embedder, context_per_hit=-1)


def test_fixture_store_returns_source_metadata() -> None:
    embedder = demo_embedder(64)
    result = hybrid_retrieve(
        demo_store(64),
        "second apron trade",
        embedder,
        top_k=2,
        candidate_k=5,
    )
    assert result.hits
    document = result.documents[0]
    assert document.title == "2023 NBA-NBPA Collective Bargaining Agreement"
    assert document.source_url == pdf_url()
    assert document.page_offset == 24
    assert document.effective_start == "2023-07-01"


def test_context_passages_count_as_retrieved() -> None:
    query = "purple marquee"
    hit = _chunk("hit", query, "1 Intro")
    neighbor = _chunk("neighbor", "quiet hallway", "2 Hallway")
    embedder = HashEmbedder(dimensions=64)
    store = MemoryChunkStore(
        [hit, neighbor],
        {"hit": embedder.embed_query(query), "neighbor": embedder.embed_query(neighbor.text)},
    )
    result = hybrid_retrieve(store, query, embedder, top_k=1, candidate_k=5)
    assert [item.id for item in result.context] == ["neighbor"]
    kept = validate_draft(
        DraftAnswer(claims=[Claim(text="Neighbor rule.", passage_ids=["neighbor"])]),
        result.passages(),
    )
    assert kept.kind == "answer"
    dropped = validate_draft(
        DraftAnswer(claims=[Claim(text="Missing.", passage_ids=["not-retrieved"])]),
        result.passages(),
    )
    assert dropped.kind == "refusal"
    assert dropped.reason == "citations_dropped"
    assert {item.id for item in result.hits}.isdisjoint(item.id for item in result.context)

    class _Drafter:
        def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer:
            return DraftAnswer(claims=[Claim(text="Neighbor rule.", passage_ids=["neighbor"])])

    response = answer_question(query, store, embedder, _Drafter(), top_k=1, candidate_k=5)
    assert response.kind == "answer"
    assert response.claims[0].passage_ids == ["neighbor"]


class _Rows:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return list(self._rows)

    def first(self) -> SimpleNamespace | None:
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self) -> None:
        self.sql: list[str] = []

    def execute(self, statement: object, params: dict[str, object] | None = None) -> _Rows:
        sql = str(statement)
        self.sql.append(sql)
        if sql == neighbor_sql():
            return _Rows(
                [
                    SimpleNamespace(slot="prev", id="left"),
                    SimpleNamespace(slot="next", id="right"),
                ]
            )
        if sql == section_candidates_sql():
            return _Rows(
                [
                    SimpleNamespace(id="exact", section="6(j) Exceptions"),
                    SimpleNamespace(id="child", section="6(j)(1) Child"),
                    SimpleNamespace(id="other", section="2(e) Elsewhere"),
                ]
            )
        if "source_documents" in sql:
            return _Rows(
                [
                    SimpleNamespace(
                        id="doc-1",
                        title="2023 CBA",
                        source_url="https://example.test/cba.pdf",
                        sha256="abc",
                        cover_date="June 28, 2023",
                        printed_term="2023-2030",
                        page_offset=24,
                        effective_start="2023-07-01",
                        effective_through="2029-30",
                    )
                ]
            )
        if sql == chunk_by_id_sql() and params and params.get("chunk_id") == "loaded":
            return _Rows(
                [
                    SimpleNamespace(
                        id="loaded",
                        article_number=7,
                        article_title="Cap",
                        section="1 Intro",
                        page_start=1,
                        page_end=2,
                        text="loaded body",
                        source_url="https://example.test/cba.pdf",
                    )
                ]
            )
        return _Rows([])


def test_context_sql_is_fixed() -> None:
    for statement in (
        neighbor_sql(),
        section_candidates_sql(),
        chunk_by_id_sql(),
        source_documents_sql(),
    ):
        assert "cba_chunks" in statement or "source_documents" in statement
        assert "{" not in statement
        assert "%s" not in statement
    assert ":chunk_id" in neighbor_sql()
    assert "article_number" in neighbor_sql()
    assert "chunk_index" in neighbor_sql()
    assert ":article" in section_candidates_sql()
    assert "IN :chunk_ids" in source_documents_sql()


def test_postgres_store_loads_neighbors_sections_and_metadata() -> None:
    session = _Session()
    cached = _chunk("cached", "cached body")
    store = PostgresChunkStore(session, {"cached": cached})
    assert store.get("cached") is cached
    assert session.sql == []
    assert store.neighbor_ids("mid") == ("left", "right")
    assert store.section_ids(7, "6(j)") == ["exact"]
    loaded = store.get("loaded")
    assert loaded is not None
    assert loaded.text == "loaded body"
    assert store.get("missing") is None
    documents = store.source_documents(["loaded"])
    assert documents[0].title == "2023 CBA"
    assert documents[0].page_offset == 24
    assert documents[0].printed_term == "2023-2030"
    assert neighbor_sql() in session.sql
    assert section_candidates_sql() in session.sql
    assert chunk_by_id_sql() in session.sql

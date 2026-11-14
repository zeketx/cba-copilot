from types import SimpleNamespace

import pytest
from app.corpus import pdf_url
from app.demo import demo_embedder, demo_store
from app.domain import Chunk, DraftAnswer, DraftClaim
from app.grounding.validate import validate_draft
from app.pipeline import answer_question
from app.retrieval.embed import HashEmbedder
from app.retrieval.hybrid import evidence_is_adequate, hybrid_retrieve
from app.retrieval.queries import (
    chunk_by_id_sql,
    context_batch_sql,
    keyword_search_sql,
    neighbor_batch_sql,
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


def test_hybrid_ranks_the_salary_definition_above_unlikely_bonus_overlap() -> None:
    salary = _chunk(
        "salary",
        '"Salary" means Compensation, not including Unlikely Bonuses.',
        '1(lll) “Salary” means',
        article=1,
    )
    distractor = _chunk(
        "bonus",
        "No Player Contract may provide for any Unlikely Bonus. Salary plus amounts.",
        "5(b)(2) Unlikely Bonus",
    )
    embedder, store = _memory([distractor, salary])
    result = hybrid_retrieve(
        store,
        "What does Salary mean, and which amounts are included when computing Team Salary?",
        embedder,
        top_k=2,
        candidate_k=5,
    )
    assert result.hits[0].id == "salary"


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
        DraftAnswer(
            claims=[
                DraftClaim(
                    text="Neighbor rule.",
                    quote="quiet hallway",
                    passage_ids=["neighbor"],
                )
            ]
        ),
        result.passages(),
    )
    assert kept.kind == "answer"
    dropped = validate_draft(
        DraftAnswer(
            claims=[
                DraftClaim(
                    text="Missing.",
                    quote="quiet hallway",
                    passage_ids=["not-retrieved"],
                )
            ]
        ),
        result.passages(),
    )
    assert dropped.kind == "refusal"
    assert dropped.reason == "citations_dropped"
    assert {item.id for item in result.hits}.isdisjoint(item.id for item in result.context)

    class _Drafter:
        def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer:
            return DraftAnswer(
                claims=[
                    DraftClaim(
                        text="Neighbor rule.",
                        quote="quiet hallway",
                        passage_ids=["neighbor"],
                    )
                ]
            )

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


def _chunk_row(chunk_id: str, section: str, *, article: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        kind="chunk",
        chunk_index=0,
        id=chunk_id,
        article_number=article,
        article_title="Cap",
        section=section,
        page_start=1,
        page_end=1,
        body="body",
        source_url="https://example.test/cba.pdf#page=1",
    )


class _Session:
    def __init__(self, search_ids: list[str] | None = None) -> None:
        self.sql: list[str] = []
        self.search_ids = search_ids or []

    def execute(self, statement: object, params: dict[str, object] | None = None) -> _Rows:
        sql = str(statement)
        self.sql.append(sql)
        if "<=>" in sql or "search_vector" in sql:
            return _Rows([SimpleNamespace(id=item) for item in self.search_ids])
        if sql == neighbor_batch_sql():
            return _Rows(
                [
                    SimpleNamespace(
                        slot="prev",
                        hit_id="hit",
                        id="left",
                        article_number=7,
                        article_title="Cap",
                        section="1 Prev",
                        page_start=1,
                        page_end=1,
                        body="previous body",
                        source_url="https://example.test/cba.pdf#page=1",
                    ),
                    SimpleNamespace(
                        slot="next",
                        hit_id="hit",
                        id="right",
                        article_number=7,
                        article_title="Cap",
                        section="3 Next",
                        page_start=1,
                        page_end=1,
                        body="next body",
                        source_url="https://example.test/cba.pdf#page=1",
                    ),
                ]
            )
        if sql == context_batch_sql():
            return _Rows(
                [
                    _chunk_row("exact", "6(j) Exceptions"),
                    _chunk_row("child", "6(j)(1) Child"),
                    _chunk_row("other", "2(e) Elsewhere"),
                    SimpleNamespace(
                        kind="document",
                        chunk_index=None,
                        id="doc-1",
                        article_number=None,
                        article_title=None,
                        section=None,
                        page_start=None,
                        page_end=None,
                        body=None,
                        source_url="https://example.test/cba.pdf",
                        title="2023 CBA",
                        sha256="abc",
                        cover_date="June 28, 2023",
                        printed_term="2023-2030",
                        page_offset=24,
                        effective_start="2023-07-01",
                        effective_through="2029-30",
                    ),
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


def _context_statements(sql: list[str]) -> list[str]:
    batched = {neighbor_batch_sql(), context_batch_sql()}
    return [statement for statement in sql if statement in batched]


def test_context_sql_is_fixed() -> None:
    for statement in (neighbor_batch_sql(), context_batch_sql(), chunk_by_id_sql()):
        assert "cba_chunks" in statement or "source_documents" in statement
        assert "{" not in statement
        assert "%s" not in statement
    assert "ANY(string_to_array(:hit_ids" in neighbor_batch_sql()
    assert "article_number" in neighbor_batch_sql()
    assert "chunk_index" in neighbor_batch_sql()
    assert "source_documents" in context_batch_sql()
    assert ":articles" in context_batch_sql()
    assert "ANY(string_to_array(:hit_ids" in context_batch_sql()


def test_postgres_store_loads_neighbors_sections_and_metadata() -> None:
    session = _Session()
    cached = _chunk("cached", "cached body")
    store = PostgresChunkStore(session, {"cached": cached})
    assert store.get("cached") is cached
    assert session.sql == []
    loaded = store.get("loaded")
    assert loaded is not None
    assert loaded.text == "loaded body"
    assert store.get("missing") is None
    hit = _chunk(
        "hit",
        "See Section 6(j) of this Article.",
        "2 Middle",
    )
    context = store.load_context([hit], [7])
    assert context.neighbors["hit"][0] is not None
    assert context.neighbors["hit"][0].id == "left"
    assert context.neighbors["hit"][1] is not None
    assert context.neighbors["hit"][1].id == "right"
    assert [chunk.id for chunk in context.articles[7]] == ["exact", "child", "other"]
    assert context.documents[0].title == "2023 CBA"
    assert context.documents[0].page_offset == 24
    assert context.documents[0].printed_term == "2023-2030"
    assert _context_statements(session.sql) == [neighbor_batch_sql(), context_batch_sql()]


def test_postgres_context_statements_do_not_grow_with_top_k() -> None:
    ids = [f"h{index}" for index in range(5)]
    chunks = []
    for index, chunk_id in enumerate(ids, start=1):
        text = f"{chunk_id} zebra quota. See Section 6(j) of this Article."
        chunks.append(_chunk(chunk_id, text, f"{index} Section"))
    counts: list[int] = []
    for top_k in (1, 5):
        session = _Session(ids)
        store = PostgresChunkStore(session, {chunk.id: chunk for chunk in chunks})
        embedder = HashEmbedder(dimensions=64)
        hybrid_retrieve(
            store,
            "zebra quota",
            embedder,
            top_k=top_k,
            candidate_k=5,
        )
        counts.append(len(_context_statements(session.sql)))
        assert chunk_by_id_sql() not in session.sql
    assert counts == [2, 2]

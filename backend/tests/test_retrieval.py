from app.domain import Chunk
from app.retrieval.embed import HashEmbedder
from app.retrieval.hybrid import evidence_is_adequate, hybrid_retrieve
from app.retrieval.queries import keyword_search_sql, vector_search_sql
from app.retrieval.store import MemoryChunkStore


def _chunk(chunk_id: str, text: str, section: str = "1") -> Chunk:
    return Chunk(
        id=chunk_id,
        article_number=7,
        article_title="Salary Cap",
        section=section,
        page_start=1,
        page_end=1,
        text=text,
        source_url="https://example.test/cba.pdf#page=1",
    )


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
    hits = hybrid_retrieve(store, "second apron trade", embedder, top_k=2, candidate_k=5)
    assert hits[0].id == "apron"
    assert evidence_is_adequate("second apron trade", hits)
    assert not evidence_is_adequate("nhl coach timeouts overtime", hits)

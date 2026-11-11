from uuid import uuid4

import pytest
from app.config import Settings
from app.retrieval.embed import HashEmbedder, OpenAIEmbedder
from ingest.load import chunk_upsert_statement, document_upsert_statement
from ingest.rows import ChunkRow, chunk_rows, references
from sqlalchemy.dialects import postgresql


def test_references_extraction_cases() -> None:
    text = (
        "See Section 6(d) of this Article and Article VII, Section 2(e)(1). "
        "Compare Section 2(e)(1) of Article VII and Section 10(a)(1) below. "
        "Article XXXIX controls. Section 6(d) of this Article repeats."
    )
    found = references(text, 7, "2. Uniform Player Contract.")
    assert found == [
        {"article": 7, "section": "6(d)"},
        {"article": 7, "section": "2(e)(1)"},
        {"article": 7, "section": "10(a)(1)"},
        {"article": 39},
    ]
    own = references("Section 2 of this Article and Section 6(d).", 7, "2. Title")
    assert own == [{"article": 7, "section": "6(d)"}]
    article_only = references("Article XXXIX ends the term.", 1, "1. Definitions")
    assert article_only == [{"article": 39}]


def test_chunk_rows_printed_viewer_and_metadata() -> None:
    markdown = (
        "<!-- pdf-page: 25 -->\n"
        "# Article I. DEFINITIONS\n"
        "## Section 1. Definitions\n"
        "See Article VII, Section 2(e)(1).\n"
        "<!-- pdf-page: 26 -->\n"
        "A later sentence on the next viewer page.\n"
    )
    rows = chunk_rows(markdown, source_url="https://example.test/cba.pdf", offset=24)
    assert len(rows) == 1
    row = rows[0]
    assert row.chunk_index == 0
    assert row.article_number == 1
    assert row.article_title == "DEFINITIONS"
    assert row.page_start == 1
    assert row.page_end == 2
    assert row.printed_page == 1
    assert row.viewer_page == 25
    assert row.source_url == "https://example.test/cba.pdf#page=25"
    assert row.metadata["slug"]
    assert row.metadata["references"] == [{"article": 7, "section": "2(e)(1)"}]


def test_hash_embedder_embed_documents_dimension() -> None:
    vectors = HashEmbedder(dimensions=32).embed_documents(["aprons", "cap"])
    assert len(vectors) == 2
    assert all(len(vector) == 32 for vector in vectors)


def test_hash_embedder_default_matches_the_column_width() -> None:
    from app.database.constants import EMBEDDING_DIMENSIONS

    vector = HashEmbedder().embed_query("apron")
    assert len(vector) == EMBEDDING_DIMENSIONS == 1024


def test_openai_embed_documents_raises_with_no_key_before_a_client(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("httpx client was built")

    monkeypatch.setattr("httpx.post", boom)
    monkeypatch.setattr("httpx.Client", boom)
    settings = Settings(openai_api_key="", _env_file=None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbedder(settings).embed_documents(["aprons"])


def test_upsert_statements_conflict_targets_omit_search_vector() -> None:
    document_sql = str(
        document_upsert_statement(
            title="CBA",
            source_url="https://example.test/cba.pdf",
            sha256="abc",
            cover_date="July 2023",
            printed_term="term",
            page_offset=24,
            effective_start="2023-07-01",
            effective_through="2029-30",
            text="# Article I. DEFINITIONS\n",
        ).compile(dialect=postgresql.dialect())
    )
    assert "ON CONFLICT" in document_sql
    assert "source_url" in document_sql
    row = ChunkRow(
        chunk_index=0,
        article_number=1,
        article_title="DEFINITIONS",
        section="1. Definitions",
        page_start=1,
        page_end=1,
        printed_page=1,
        viewer_page=25,
        source_url="https://example.test/cba.pdf#page=25",
        text="body",
        metadata={"slug": "a1-1", "references": []},
    )
    compiled = chunk_upsert_statement(uuid4(), [row]).compile(dialect=postgresql.dialect())
    chunk_sql = str(compiled)
    assert "ON CONFLICT" in chunk_sql
    assert "document_id" in chunk_sql
    assert "chunk_index" in chunk_sql
    assert "search_vector" not in chunk_sql
    assert "IS DISTINCT FROM" in chunk_sql
    insert_prefix = chunk_sql.split("ON CONFLICT", 1)[0]
    assert "search_vector" not in insert_prefix

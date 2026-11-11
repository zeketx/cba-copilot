import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.config import Settings
from app.domain import Chunk
from app.retrieval.store import PostgresChunkStore
from evals.embed_bench import (
    HASH_MODEL,
    KEY_REQUIRED,
    LIVE_REQUIRED,
    catalog_from_payload,
    embed_corpus,
    main,
    pick_source_document,
    resolve_price,
)
from evals.metrics import (
    ExpectedSection,
    chunk_matches,
    lenient_chunk_matches,
    section_for_match,
    section_matches,
)

ROOT = Path(__file__).resolve().parents[2]


def _chunk(chunk_id: str, article: int, section: str, text: str, title: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        article_number=article,
        article_title=title,
        section=section,
        page_start=1,
        page_end=1,
        text=text,
        source_url="https://example.test/cba.pdf#page=1",
    )


def _corpus() -> list[Chunk]:
    return [
        _chunk(
            "tax",
            7,
            "6(f)(1) Taxpayer Mid-Level",
            "taxpayer mid-level exception five million",
            "Exceptions",
        ),
        _chunk(
            "apron",
            7,
            "2(e)(4) Transaction Restrictions",
            "second apron aggregation cash",
            "Aprons",
        ),
        _chunk(
            "bird",
            1,
            "1(yy) Qualifying Veteran Free Agent",
            "qualifying veteran free agent three seasons",
            "Definitions",
        ),
    ]


class ScriptedEmbedder:
    def __init__(self) -> None:
        self.document_calls = 0
        self.prompt_tokens = 0
        self.model = "qwen/qwen3-embedding-8b"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        self.prompt_tokens += len(texts)
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.prompt_tokens += 1
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        if "taxpayer" in lowered:
            return [1.0, 0.0, 0.0]
        if "apron" in lowered or "aggregation" in lowered:
            return [0.0, 1.0, 0.0]
        if "bird" in lowered or "qualifying veteran" in lowered:
            return [0.0, 0.0, 1.0]
        return [0.1, 0.1, 0.1]


def _questions(path: Path) -> None:
    path.write_text(
        """
- id: taxpayer
  draft: true
  question: How large is the taxpayer mid-level exception?
  expect: answer
  match: any
  articles:
    - article: 7
      section_contains: "6(f)(1)"
- id: bird
  draft: true
  question: Explain Bird rights.
  expect: answer
  match: any
  articles:
    - article: 1
      section_contains: "1(yy)"
- id: wrong-article
  draft: true
  question: How large is the taxpayer mid-level exception?
  expect: answer
  match: any
  articles:
    - article: 1
      section_contains: "1(yy)"
- id: skipped
  question: How many timeouts may an NHL coach call?
  expect: refusal
  match: any
  articles: []
""",
        encoding="utf-8",
    )


def test_ingest_labels_map_onto_question_needles() -> None:
    bird = '1. Definitions / (yy) “Qualifying Veteran Free Agent” means three seasons'
    minimum = '1. Definitions / (ll) “Minimum Team Salary” means the Article VII amount'
    team = '1. Definitions / (uuu) “Team Salary” means the sum part 2'
    early = '1. Definitions / (t) “Early Qualifying Veteran Free Agent” means two seasons'
    doubled = '1. Definitions / (tt) “Something Else” means another term'
    apron = '2. Salary Cap / (e) (1) “Apron Team Salary” shall mean Team Salary plus bonuses'
    tight = "6. Exceptions / (j)(1)(i) Standard exception brings back salary"
    spaced = "8. Trade Rules / (e) (1) Subject to Section 2(e), a veteran may sign and trade"
    plain = "4. Determination of Team Salary"
    assert section_matches(section_for_match(bird), "1(yy)")
    assert section_matches(section_for_match(minimum), "1(ll)")
    assert section_matches(section_for_match(team), "1(uuu)")
    assert not section_matches(section_for_match(minimum), "1(l)")
    assert not section_matches(section_for_match(team), "1(u)")
    assert section_matches(section_for_match(early), "1(t)")
    assert not section_matches(section_for_match(doubled), "1(t)")
    assert section_matches(section_for_match(apron), '2(e)(1) “Apron Team Salary”')
    assert section_matches(section_for_match(tight), "6(j)(1)(i)")
    assert section_matches(section_for_match(spaced), "8(e) (1)")
    assert section_matches(section_for_match(plain), "4 Determination of Team Salary")
    assert section_for_match("1(yy) Qualifying Veteran Free Agent") == (
        "1(yy) Qualifying Veteran Free Agent"
    )
    assert section_matches(section_for_match("2(e)(4) Transaction"), "2(e)")


def test_lenient_match_accepts_a_parent_label_only_with_the_text_marker() -> None:
    parent = _chunk(
        "mle",
        7,
        "6. Exceptions to the Salary Cap / (e) Non-Taxpayer Mid-Level Salary Exception",
        "(1) Contracts signed under it can total 9.12 percent of the salary cap.",
        "Exceptions",
    )
    bare = _chunk(
        "bare",
        7,
        "6. Exceptions to the Salary Cap / (e) Non-Taxpayer Mid-Level Salary Exception",
        "The exception opens after the moratorium and names no numbered child.",
        "Exceptions",
    )
    expected = ExpectedSection(article=7, section_contains="6(e)(1)")
    assert not chunk_matches(parent, expected)
    assert lenient_chunk_matches(parent, expected)
    assert not chunk_matches(bare, expected)
    assert not lenient_chunk_matches(bare, expected)
    traded = _chunk(
        "trade",
        7,
        "6. Exceptions to the Salary Cap / (j) Traded Player Exception",
        "(1) A Team may replace a player. (i) Incoming salary is 100 percent plus $250,000.",
        "Exceptions",
    )
    both = ExpectedSection(article=7, section_contains="6(j)(1)(i)")
    only_roman = _chunk(
        "roman",
        7,
        "6. Exceptions to the Salary Cap / (j) Traded Player Exception",
        "(i) This romanette has no numbered parent in the text.",
        "Exceptions",
    )
    assert lenient_chunk_matches(traded, both)
    assert not lenient_chunk_matches(only_roman, both)
    deeper = ExpectedSection(article=8, section_contains="1(c)(ii)")
    rookie = _chunk(
        "rookie",
        8,
        "1. Rookie Scale / (c) Protection",
        "(i) A shorter child. (ii) Protection is 80 percent of the rookie scale amount.",
        "Rookie",
    )
    only_i = _chunk(
        "only-i",
        8,
        "1. Rookie Scale / (c) Protection",
        "(i) A shorter child stays here.",
        "Rookie",
    )
    assert lenient_chunk_matches(rookie, deeper)
    assert not lenient_chunk_matches(only_i, deeper)
    assert not lenient_chunk_matches(
        _chunk(rookie.id, 2, rookie.section, rookie.text, rookie.article_title),
        deeper,
    )


def test_lenient_label_match_joins_pdf_spaces_inside_words() -> None:
    spaced = _chunk(
        "bird-exception",
        7,
        "6. Exceptions to the Salary Cap / (b) V eteran Free Agen t Exception",
        "The exception begins at 12:01 p.m. eastern time.",
        "Exceptions",
    )
    expected = ExpectedSection(article=7, section_contains="6(b) Veteran")
    assert not chunk_matches(spaced, expected)
    assert lenient_chunk_matches(spaced, expected)
    untouched = _chunk(
        "free-agent",
        7,
        "6. Exceptions to the Salary Cap / (b) Free Agent Exception",
        "No veteran wording here.",
        "Exceptions",
    )
    assert not lenient_chunk_matches(untouched, expected)


def test_section_match_stops_at_a_longer_id() -> None:
    assert section_matches("1(t) Early Bird", "1(t)")
    assert not section_matches("1(tt) Something", "1(t)")
    assert section_matches("2(e)(4) Transaction", "2(e)")
    assert not section_matches("16(a) Later", "6")
    assert section_matches("6(a) Award Eligibility", "6(a) Award")
    assert not section_matches("6(a)(i) Minutes", "6(a) Award")


def test_catalog_price_is_dollars_per_million_tokens() -> None:
    catalog = catalog_from_payload(
        {
            "data": [
                {
                    "id": "qwen/qwen3-embedding-8b",
                    "context_length": 40960,
                    "pricing": {"prompt": "0.00000001"},
                }
            ]
        }
    )
    price, source, context = resolve_price("qwen/qwen3-embedding-8b", catalog)
    assert price == pytest.approx(0.01)
    assert source == "openrouter"
    assert context == 40960
    pinned, pinned_source, _context = resolve_price("mongodb/voyage-4-lite", {})
    assert pinned == pytest.approx(0.02)
    assert pinned_source == "pinned"
    free, free_source, free_context = resolve_price(HASH_MODEL, catalog)
    assert free == 0
    assert free_source == "free"
    assert free_context is None


def test_cached_corpus_is_not_embedded_again(tmp_path: Path) -> None:
    embedder = ScriptedEmbedder()
    chunks = _corpus()
    cache = tmp_path / "cache.json"
    _vectors, dimensions, total, this_run = embed_corpus(embedder, chunks, cache, dimensions=None)
    assert embedder.document_calls == 1
    assert this_run == 3
    assert total == 3
    assert dimensions == 3
    again = ScriptedEmbedder()
    _vectors, _dimensions, total, this_run = embed_corpus(again, chunks, cache, dimensions=3)
    assert again.document_calls == 0
    assert this_run == 0
    assert total == 3


def test_bench_scores_dense_and_hybrid_without_network(tmp_path: Path) -> None:
    questions = tmp_path / "questions.yaml"
    _questions(questions)
    embedder = ScriptedEmbedder()
    code = main(
        [
            "--live",
            "--models",
            "qwen/qwen3-embedding-8b",
            "--questions",
            str(questions),
            "--report-dir",
            str(tmp_path / "reports"),
        ],
        corpus=_corpus(),
        settings=Settings(openrouter_api_key="test-key"),
        fetch_catalog=lambda: {},
        embedder_for_model=lambda _model: embedder,
    )
    assert code == 0
    report = json.loads((tmp_path / "reports" / "embed-bench.json").read_text(encoding="utf-8"))
    models = {item["model"]: item for item in report["models"]}
    assert set(models) == {HASH_MODEL, "qwen/qwen3-embedding-8b"}
    qwen = models["qwen/qwen3-embedding-8b"]
    assert qwen["error"] is None
    assert qwen["dense"]["recall_at_5"] == pytest.approx(2 / 3)
    assert qwen["hybrid"]["recall_at_5"] == pytest.approx(2 / 3)
    assert "wrong-article" in qwen["misses"]
    assert "taxpayer" not in qwen["misses"]
    assert "skipped" in qwen["skipped"]
    assert qwen["price_source"] == "pinned"
    markdown = (tmp_path / "reports" / "embed-bench.md").read_text(encoding="utf-8")
    assert "hybrid R@5" in markdown
    assert "Dense search ranks" in markdown


def test_second_live_run_does_not_reembed_the_corpus(tmp_path: Path) -> None:
    questions = tmp_path / "questions.yaml"
    _questions(questions)
    first = ScriptedEmbedder()
    args = [
        "--live",
        "--models",
        "qwen/qwen3-embedding-8b",
        "--questions",
        str(questions),
        "--report-dir",
        str(tmp_path / "reports"),
    ]
    settings = Settings(openrouter_api_key="test-key")
    assert (
        main(
            args,
            corpus=_corpus(),
            settings=settings,
            fetch_catalog=lambda: {},
            embedder_for_model=lambda _model: first,
        )
        == 0
    )
    second = ScriptedEmbedder()
    assert (
        main(
            args,
            corpus=_corpus(),
            settings=settings,
            fetch_catalog=lambda: {},
            embedder_for_model=lambda _model: second,
        )
        == 0
    )
    assert second.document_calls == 0
    report = json.loads((tmp_path / "reports" / "embed-bench.json").read_text(encoding="utf-8"))
    qwen = next(item for item in report["models"] if item["model"] == "qwen/qwen3-embedding-8b")
    assert qwen["index_tokens_this_run"] == 0
    assert qwen["index_cost_this_run_usd"] == 0


def test_remote_models_without_live_do_not_fetch(capsys: pytest.CaptureFixture[str]) -> None:
    def explode():
        raise AssertionError("network")

    code = main(
        ["--models", "qwen/qwen3-embedding-8b"],
        fetch_catalog=explode,
    )
    assert code == 2
    assert LIVE_REQUIRED in capsys.readouterr().err


def test_live_without_a_key_exits_before_a_request(capsys: pytest.CaptureFixture[str]) -> None:
    def explode():
        raise AssertionError("network")

    code = main(
        ["--live", "--models", "mongodb/voyage-4-lite"],
        settings=Settings(openrouter_api_key=""),
        fetch_catalog=explode,
    )
    assert code == 2
    assert KEY_REQUIRED in capsys.readouterr().err


def test_missing_pdf_names_the_download_script(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["--models", HASH_MODEL, "--pdf", str(tmp_path / "missing.pdf")],
        fetch_catalog=lambda: (_ for _ in ()).throw(AssertionError("network")),
    )
    assert code == 2
    assert "download_cba.py" in capsys.readouterr().err


def test_check_questions_fails_when_a_draft_section_is_absent(tmp_path: Path) -> None:
    questions = tmp_path / "questions.yaml"
    _questions(questions)
    missing = main(
        ["--check-questions", "--questions", str(questions)],
        corpus=[_corpus()[0]],
    )
    assert missing == 1
    found = main(
        ["--check-questions", "--questions", str(questions)],
        corpus=_corpus(),
    )
    assert found == 0


def test_reports_directory_is_gitignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "backend/evals/reports/" in ignore


def test_draft_questions_are_marked_and_do_not_reuse_harness_ids() -> None:
    import yaml

    draft_path = ROOT / "backend" / "evals" / "draft_questions.yaml"
    original_path = ROOT / "backend" / "evals" / "questions.yaml"
    draft = yaml.safe_load(draft_path.read_text(encoding="utf-8"))
    original = yaml.safe_load(original_path.read_text(encoding="utf-8"))
    assert len(original) == 6
    assert len(draft) >= 25
    original_ids = {item["id"] for item in original}
    for item in draft:
        assert item["draft"] is True
        assert item["expect"] == "answer"
        assert item["id"] not in original_ids
        assert item["articles"]
        assert item["articles"][0]["section_contains"]
        assert item["articles"][0]["verified"] is True


def test_pick_source_document_uses_the_one_row_or_the_corpus_url() -> None:
    only = pick_source_document([("doc-1", "https://other.example/cba.pdf")], set())
    assert only == "doc-1"
    chosen = pick_source_document(
        [
            ("doc-1", "https://other.example/cba.pdf"),
            ("doc-2", "https://corpus.example/cba.pdf"),
        ],
        {"https://corpus.example/cba.pdf"},
    )
    assert chosen == "doc-2"
    with pytest.raises(RuntimeError, match="none match"):
        pick_source_document(
            [("doc-1", "https://a.example"), ("doc-2", "https://b.example")],
            {"https://corpus.example/cba.pdf"},
        )
    with pytest.raises(RuntimeError, match="No source_documents"):
        pick_source_document([], set())


def test_database_without_url_or_key_does_not_connect(monkeypatch, capsys) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("database opened")

    monkeypatch.setattr("evals.embed_bench.open_database", boom)
    monkeypatch.setattr("httpx.Client", boom)
    missing_url = main(["--database"], settings=Settings(database_url="", _env_file=None))
    assert missing_url == 2
    assert "No connection was opened" in capsys.readouterr().err
    missing_key = main(
        ["--database"],
        settings=Settings(
            database_url="postgresql://postgres:pw@127.0.0.1:5432/cba",
            embedding_provider="openrouter",
            embedding_model="mongodb/voyage-4-lite",
            openrouter_api_key="",
            _env_file=None,
        ),
    )
    assert missing_key == 2
    error = capsys.readouterr().err
    assert "OPENROUTER_API_KEY" in error
    assert "No request was sent" in error


def test_in_memory_bench_does_not_open_the_database(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("database opened")

    monkeypatch.setattr("evals.embed_bench.open_database", boom)
    questions = tmp_path / "questions.yaml"
    _questions(questions)
    code = main(
        ["--models", HASH_MODEL, "--questions", str(questions), "--report-dir", str(tmp_path)],
        corpus=_corpus(),
        settings=Settings(_env_file=None),
    )
    assert code == 0


def test_database_flag_scores_ingest_labels(tmp_path, monkeypatch, capsys) -> None:
    bird = _chunk(
        "bird-id",
        1,
        "1. Definitions / (yy) “Qualifying Veteran Free Agent” means three seasons",
        "qualifying veteran free agent bird rights three seasons",
        "Definitions",
    )
    apron = _chunk(
        "apron-id",
        7,
        "2. Salary Cap / (e)(4) restrictions table",
        "second apron aggregation cash",
        "Aprons",
    )
    other = _chunk(
        "other-id",
        7,
        "6. Exceptions / (f) Taxpayer mid-level",
        "taxpayer mid-level exception five million",
        "Exceptions",
    )
    chunks = [bird, apron, other]

    class _Result:
        def __init__(self, ids: list[str]) -> None:
            self._ids = ids

        def all(self):
            return [SimpleNamespace(id=item) for item in self._ids]

    class _Session:
        def __init__(self) -> None:
            self.sql: list[str] = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.sql.append(sql)
            if "search_vector" in sql:
                return _Result(["apron-id", "bird-id", "other-id"])
            return _Result(["bird-id", "other-id", "apron-id"])

        def close(self) -> None:
            return None

    class _Engine:
        def dispose(self) -> None:
            return None

    session = _Session()
    store = PostgresChunkStore(session, {chunk.id: chunk for chunk in chunks})

    def open_fake(_settings):
        return session, store, chunks, _Engine()

    monkeypatch.setattr("evals.embed_bench.open_database", open_fake)
    questions = tmp_path / "questions.yaml"
    questions.write_text(
        """
- id: bird
  draft: true
  question: What makes a player a Qualifying Veteran Free Agent?
  expect: answer
  match: any
  articles:
    - article: 1
      section_contains: "1(yy)"
- id: missing-minimum
  draft: true
  question: Where does the agreement send you for the Minimum Team Salary amount?
  expect: answer
  match: any
  articles:
    - article: 1
      section_contains: "1(ll)"
- id: apron
  question: Which transactions does the restrictions table mark at the second apron?
  expect: answer
  match: any
  articles:
    - article: 7
      section_contains: "2(e)(4)"
- id: skipped
  question: How many timeouts may an NHL coach call?
  expect: refusal
  articles: []
""",
        encoding="utf-8",
    )
    code = main(
        ["--database", "--questions", str(questions), "--report-dir", str(tmp_path / "reports")],
        settings=Settings(
            database_url="postgresql://postgres:pw@127.0.0.1:5432/cba",
            embedding_provider="hash",
            _env_file=None,
        ),
    )
    assert code == 0
    assert "1(yy)" not in bird.section
    assert any("cba_chunks" in sql and "embedding" in sql for sql in session.sql)
    assert any("search_vector" in sql for sql in session.sql)
    report = json.loads((tmp_path / "reports" / "embed-bench.json").read_text(encoding="utf-8"))
    scored = report["models"][0]
    assert scored["latency_scope"] == "hybrid_retrieve"
    assert scored["draft_hybrid"]["recall_at_5"] == pytest.approx(0.5)
    assert scored["draft_hybrid"]["recall_at_8"] == pytest.approx(0.5)
    assert scored["hybrid"]["recall_at_5"] == pytest.approx(2 / 3)
    assert scored["question_count"] == 3
    assert scored["draft_question_count"] == 2
    assert scored["existing_question_count"] == 1
    assert "skipped" in scored["skipped"]
    assert any(item.startswith("missing-minimum:") for item in scored["miss_labels"])
    assert not any(item.startswith("bird:") for item in scored["miss_labels"])
    stdout = capsys.readouterr().out
    assert "strict draft" in stdout
    assert "lenient draft" in stdout
    assert "strict all" in stdout
    assert "lenient all" in stdout
    assert scored["lenient_draft_hybrid"]["recall_at_5"] == pytest.approx(0.5)
    assert scored["lenient_flips"] == []
    assert "query p95" in stdout
    assert "hybrid_retrieve" in stdout

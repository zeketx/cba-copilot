import json
from pathlib import Path

import pytest
from app.config import Settings
from app.domain import Chunk
from evals.embed_bench import (
    HASH_MODEL,
    KEY_REQUIRED,
    LIVE_REQUIRED,
    catalog_from_payload,
    embed_corpus,
    main,
    resolve_price,
)
from evals.metrics import section_matches

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

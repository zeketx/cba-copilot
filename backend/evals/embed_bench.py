from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx
import yaml
from app.config import Settings
from app.corpus import load_corpus, pdf_url
from app.database.constants import EMBEDDING_DIMENSIONS
from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.embed import (
    Embedder,
    HashEmbedder,
    OpenRouterEmbedder,
    build_embedder,
    voyage_input_type,
)
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.hybrid import hybrid_retrieve
from app.retrieval.store import ChunkStore, MemoryChunkStore, PostgresChunkStore
from ingest.cba_text import chunk_cba_text, read_pdf_layout

from evals.metrics import (
    BenchQuestion,
    ExpectedSection,
    RankMetrics,
    aggregate,
    chunk_matches,
    first_relevant_rank,
    lenient_chunk_matches,
    percentile,
    recall_at,
)

HASH_MODEL = "hash"
QUESTIONS_PATH = Path(__file__).with_name("questions.yaml")
DRAFT_PATH = Path(__file__).with_name("draft_questions.yaml")
REPORT_DIR = Path(__file__).with_name("reports")
PDF_PATH = Path(__file__).resolve().parents[2] / "data" / "downloads" / "2023-nba-cba.pdf"
MODELS_URL = "https://openrouter.ai/api/v1/models"
PINNED_USD_PER_MILLION = {
    "qwen/qwen3-embedding-8b": 0.01,
    "mongodb/voyage-4-lite": 0.02,
    "mongodb/voyage-4": 0.06,
}
PINNED_CONTEXT = {
    "qwen/qwen3-embedding-8b": 40960,
    "mongodb/voyage-4-lite": 32000,
    "mongodb/voyage-4": 32000,
}

LIVE_REQUIRED = (
    "Refusing to call OpenRouter without --live. "
    "Re-run with --live after OPENROUTER_API_KEY is set."
)
KEY_REQUIRED = (
    "OPENROUTER_API_KEY is required to embed with OpenRouter. "
    "Set it in the environment or backend/.env. No request was sent."
)
DATABASE_URL_REQUIRED = (
    "DATABASE_URL is required to score the live store. No connection was opened."
)


class PricedEmbedder(Protocol):
    prompt_tokens: int

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class CatalogEntry:
    price_per_million: float
    context_length: int | None


@dataclass
class ModelReport:
    model: str
    dimensions: int | None
    chunk_count: int
    question_count: int
    draft_question_count: int
    existing_question_count: int
    unscored: list[str]
    unmatched: list[str]
    skipped: list[str]
    dense: RankMetrics | None
    hybrid: RankMetrics | None
    draft_dense: RankMetrics | None
    draft_hybrid: RankMetrics | None
    existing_dense: RankMetrics | None
    existing_hybrid: RankMetrics | None
    index_tokens: int
    index_tokens_this_run: int
    query_tokens: int
    price_per_million: float | None
    price_source: str
    index_cost_usd: float | None
    index_cost_this_run_usd: float | None
    per_1k_queries_usd: float | None
    query_latency_p50_ms: float | None
    query_latency_p95_ms: float | None
    query_count: int
    context_length: int | None
    storage_float32_bytes: int | None
    cache_bytes: int
    misses: list[str]
    error: str | None = None
    miss_labels: list[str] = field(default_factory=list)
    latency_scope: str = "embed_query"
    lenient_hybrid: RankMetrics | None = None
    lenient_draft_hybrid: RankMetrics | None = None
    lenient_flips: list[str] = field(default_factory=list)


def load_bench_questions(paths: list[Path]) -> tuple[list[BenchQuestion], list[str]]:
    questions: list[BenchQuestion] = []
    skipped: list[str] = []
    for path in paths:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"{path.name} must be a list of questions")
        for item in loaded:
            if not isinstance(item, dict):
                raise ValueError(f"{path.name} has a question that is not a mapping")
            question_id = str(item["id"])
            expect = str(item.get("expect", "answer"))
            if expect != "answer":
                skipped.append(question_id)
                continue
            articles = item.get("articles") or []
            expected: list[ExpectedSection] = []
            for article in articles:
                expected.append(
                    ExpectedSection(
                        article=int(article["article"]),
                        section_contains=str(article["section_contains"]),
                    )
                )
            if not expected:
                skipped.append(question_id)
                continue
            match = str(item.get("match", "any"))
            if match not in {"any", "all"}:
                raise ValueError(f"{question_id} match must be any or all")
            questions.append(
                BenchQuestion(
                    id=question_id,
                    question=str(item["question"]),
                    match=match,
                    draft=bool(item.get("draft", False)),
                    expected=tuple(expected),
                )
            )
    return questions, skipped


def content_hash(chunk: Chunk) -> str:
    payload = f"{chunk.article_number}\n{chunk.section}\n{chunk.text}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(report_dir: Path, model: str) -> Path:
    slug = model.replace("/", "--")
    if voyage_input_type(model, "document") is not None:
        slug = f"{slug}--document"
    return report_dir / "cache" / f"{slug}.json"


def _read_cache(path: Path, *, dimensions: int | None) -> tuple[dict[str, list[float]], int]:
    if not path.exists():
        return {}, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    if dimensions is not None and payload.get("dimensions") not in {None, dimensions}:
        return {}, 0
    entries = payload.get("entries") or {}
    vectors: dict[str, list[float]] = {}
    for key, entry in entries.items():
        raw = entry.get("vector") or []
        vectors[key] = [float(value) for value in raw]
    return vectors, int(payload.get("prompt_tokens") or 0)


def _write_cache(
    path: Path,
    *,
    model: str,
    dimensions: int,
    vectors: dict[str, list[float]],
    prompt_tokens: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {
            "model": model,
            "dimensions": dimensions,
            "prompt_tokens": prompt_tokens,
            "entries": {
                key: {"vector": vector} for key, vector in sorted(vectors.items())
            },
        },
        ensure_ascii=False,
    )
    _replace(path, body)


def embed_corpus(
    embedder: PricedEmbedder,
    chunks: list[Chunk],
    cache_path: Path,
    *,
    dimensions: int | None,
) -> tuple[dict[str, list[float]], int, int, int]:
    cached, stored_tokens = _read_cache(cache_path, dimensions=dimensions)
    by_id: dict[str, list[float]] = {}
    missing: list[Chunk] = []
    for chunk in chunks:
        key = content_hash(chunk)
        vector = cached.get(key)
        if vector is None:
            missing.append(chunk)
            continue
        if dimensions is not None and len(vector) != dimensions:
            missing.append(chunk)
            continue
        by_id[chunk.id] = vector
    before = int(getattr(embedder, "prompt_tokens", 0))
    if missing:
        fresh = _embed_many(embedder, [chunk.text for chunk in missing])
        if len(fresh) != len(missing):
            raise RuntimeError("The embedder returned a different number of vectors than chunks.")
        for chunk, vector in zip(missing, fresh, strict=True):
            cached[content_hash(chunk)] = vector
            by_id[chunk.id] = vector
        dimensions = len(fresh[0])
    elif by_id:
        dimensions = len(next(iter(by_id.values())))
    added = int(getattr(embedder, "prompt_tokens", 0)) - before
    total_tokens = stored_tokens + added
    if dimensions is None:
        raise RuntimeError("The embedder returned no vectors.")
    _write_cache(
        cache_path,
        model=getattr(embedder, "model", HASH_MODEL),
        dimensions=dimensions,
        vectors=cached,
        prompt_tokens=total_tokens,
    )
    return by_id, dimensions, total_tokens, added


def _embed_many(embedder: PricedEmbedder, texts: list[str]) -> list[list[float]]:
    batch = getattr(embedder, "embed_documents", None)
    if callable(batch):
        return batch(texts)
    return [embedder.embed_query(text) for text in texts]


def rank_dense(
    chunks: list[Chunk],
    vectors: dict[str, list[float]],
    query: list[float],
) -> list[Chunk]:
    store = MemoryChunkStore(chunks, vectors)
    order = {chunk.id: chunk for chunk in chunks}
    found = store.vector_search(query, len(chunks))
    return [order[chunk_id] for chunk_id in found if chunk_id in order]


def rank_hybrid(
    chunks: list[Chunk],
    vectors: dict[str, list[float]],
    expanded: str,
    query: list[float],
    *,
    candidate_k: int,
    rrf_k: int,
) -> list[Chunk]:
    store = MemoryChunkStore(chunks, vectors)
    vector_ids = store.vector_search(query, candidate_k)
    keyword_ids = store.keyword_search(expanded, candidate_k)
    fused = reciprocal_rank_fusion([vector_ids, keyword_ids], k=rrf_k)
    order = {chunk.id: chunk for chunk in chunks}
    return [order[chunk_id] for chunk_id, _score in fused if chunk_id in order]


def _unmatched(chunks: list[Chunk], questions: list[BenchQuestion]) -> list[str]:
    missing: list[str] = []
    for question in questions:
        for expected in question.expected:
            found = any(chunk_matches(chunk, expected) for chunk in chunks)
            if not found:
                label = f"{question.id} article {expected.article} {expected.section_contains}"
                missing.append(label)
    return missing


def matching_chunks(chunks: list[Chunk], question: BenchQuestion) -> list[Chunk]:
    return [
        chunk
        for chunk in chunks
        if any(chunk_matches(chunk, expected) for expected in question.expected)
    ]


def score_model(
    *,
    model: str,
    embedder: PricedEmbedder,
    chunks: list[Chunk],
    questions: list[BenchQuestion],
    skipped: list[str],
    cache_path: Path,
    candidate_k: int,
    rrf_k: int,
    price_per_million: float | None,
    price_source: str,
    context_length: int | None,
    dimensions_hint: int | None = None,
) -> ModelReport:
    try:
        vectors, dimensions, index_tokens, index_this_run = embed_corpus(
            embedder,
            chunks,
            cache_path,
            dimensions=dimensions_hint,
        )
        scored: list[BenchQuestion] = []
        unscored: list[str] = []
        unmatched = _unmatched(chunks, questions)
        dense_rankings: dict[str, list[Chunk]] = {}
        hybrid_rankings: dict[str, list[Chunk]] = {}
        latencies: list[float] = []
        misses: list[str] = []
        query_before = int(getattr(embedder, "prompt_tokens", 0))
        for question in questions:
            if not matching_chunks(chunks, question):
                unscored.append(question.id)
                continue
            expanded = expand_query(question.question)
            started = time.perf_counter()
            query = embedder.embed_query(expanded)
            elapsed_ms = (time.perf_counter() - started) * 1000
            latencies.append(elapsed_ms)
            dense = rank_dense(chunks, vectors, query)
            hybrid = rank_hybrid(
                chunks,
                vectors,
                expanded,
                query,
                candidate_k=candidate_k,
                rrf_k=rrf_k,
            )
            dense_rankings[question.id] = dense
            hybrid_rankings[question.id] = hybrid
            scored.append(question)
            if first_relevant_rank(dense, question) is None:
                misses.append(question.id)
        query_tokens = int(getattr(embedder, "prompt_tokens", 0)) - query_before
        draft = [question for question in scored if question.draft]
        existing = [question for question in scored if not question.draft]
        per_question = query_tokens / len(scored) if scored else 0
        return ModelReport(
            model=model,
            dimensions=dimensions,
            chunk_count=len(chunks),
            question_count=len(scored),
            draft_question_count=len(draft),
            existing_question_count=len(existing),
            unscored=unscored,
            unmatched=unmatched,
            skipped=skipped,
            dense=aggregate(scored, dense_rankings),
            hybrid=aggregate(scored, hybrid_rankings),
            draft_dense=aggregate(draft, dense_rankings) if draft else None,
            draft_hybrid=aggregate(draft, hybrid_rankings) if draft else None,
            existing_dense=aggregate(existing, dense_rankings) if existing else None,
            existing_hybrid=aggregate(existing, hybrid_rankings) if existing else None,
            index_tokens=index_tokens,
            index_tokens_this_run=index_this_run,
            query_tokens=query_tokens,
            price_per_million=price_per_million,
            price_source=price_source,
            index_cost_usd=_usd(index_tokens, price_per_million),
            index_cost_this_run_usd=_usd(index_this_run, price_per_million),
            per_1k_queries_usd=_usd(per_question * 1000, price_per_million),
            query_latency_p50_ms=percentile(latencies, 50) if latencies else None,
            query_latency_p95_ms=percentile(latencies, 95) if latencies else None,
            query_count=len(latencies),
            context_length=context_length,
            storage_float32_bytes=len(chunks) * dimensions * 4,
            cache_bytes=cache_path.stat().st_size if cache_path.exists() else 0,
            misses=misses,
            miss_labels=hybrid_miss_labels(scored, hybrid_rankings),
            lenient_hybrid=aggregate(
                scored, hybrid_rankings, matches=lenient_chunk_matches
            ),
            lenient_draft_hybrid=(
                aggregate(draft, hybrid_rankings, matches=lenient_chunk_matches)
                if draft
                else None
            ),
            lenient_flips=lenient_flip_lines(scored, hybrid_rankings),
        )
    except RuntimeError as exc:
        return _failed(model, chunks, skipped, price_source, str(exc))


def _failed(
    model: str,
    chunks: list[Chunk],
    skipped: list[str],
    price_source: str,
    message: str,
) -> ModelReport:
    return ModelReport(
        model=model,
        dimensions=None,
        chunk_count=len(chunks),
        question_count=0,
        draft_question_count=0,
        existing_question_count=0,
        unscored=[],
        unmatched=[],
        skipped=skipped,
        dense=None,
        hybrid=None,
        draft_dense=None,
        draft_hybrid=None,
        existing_dense=None,
        existing_hybrid=None,
        index_tokens=0,
        index_tokens_this_run=0,
        query_tokens=0,
        price_per_million=None,
        price_source=price_source,
        index_cost_usd=None,
        index_cost_this_run_usd=None,
        per_1k_queries_usd=None,
        query_latency_p50_ms=None,
        query_latency_p95_ms=None,
        query_count=0,
        context_length=None,
        storage_float32_bytes=None,
        cache_bytes=0,
        misses=[],
        error=message,
    )


def _usd(tokens: float, price_per_million: float | None) -> float | None:
    if price_per_million is None:
        return None
    return tokens / 1_000_000 * price_per_million


def catalog_from_payload(payload: object) -> dict[str, CatalogEntry]:
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("data")
    if not isinstance(rows, list):
        return {}
    found: dict[str, CatalogEntry] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
        prompt = pricing.get("prompt")
        if prompt is None:
            continue
        context = row.get("context_length")
        found[row["id"]] = CatalogEntry(
            price_per_million=float(prompt) * 1_000_000,
            context_length=int(context) if isinstance(context, int) else None,
        )
    return found


def fetch_model_catalog() -> dict[str, CatalogEntry]:
    response = httpx.get(MODELS_URL, params={"output_modalities": "embeddings"}, timeout=30.0)
    response.raise_for_status()
    return catalog_from_payload(response.json())


def resolve_price(
    model: str,
    catalog: dict[str, CatalogEntry],
) -> tuple[float | None, str, int | None]:
    if model == HASH_MODEL:
        return 0.0, "free", None
    entry = catalog.get(model)
    if entry is not None:
        return entry.price_per_million, "openrouter", entry.context_length
    if model in PINNED_USD_PER_MILLION:
        return PINNED_USD_PER_MILLION[model], "pinned", PINNED_CONTEXT.get(model)
    return None, "unavailable", None


def render_markdown(reports: list[ModelReport], *, price_fetch: str, generated_at: str) -> str:
    lines = [
        "# Embedding bench",
        "",
        f"Generated {generated_at}. Price catalog {price_fetch}.",
        "",
        (
            "Dense search ranks every chunk by cosine and drops scores at or below zero, "
            "the same rule as the in-memory store."
        ),
        (
            "Hybrid search takes the top candidate list from that ranking and from "
            "token-overlap keyword search, then fuses them with reciprocal rank fusion."
        ),
        (
            "Recall is the mean across scored questions. "
            "`any` scores 1 when one expected section is inside the cutoff. "
            "`all` scores the fraction of expected sections found."
        ),
        (
            "A section matches when the article number is the same and "
            "`section_contains` meets the chunk label on a boundary, "
            "so `1(t)` does not hit `1(tt)`."
        ),
        (
            "Index cost uses the token total stored for the corpus. "
            "A full cache hit adds zero dollars on this run."
        ),
        _latency_sentence(reports),
        "",
        (
            "| model | dims | dense R@5 | hybrid R@5 | dense R@8 | hybrid R@8 | "
            "dense MRR | hybrid MRR | index $ | this run $ | per 1k queries $ | "
            "p50 ms | p95 ms | float32 bytes |"
        ),
        (
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | ---: | ---: |"
        ),
    ]
    for report in reports:
        if report.error or report.hybrid is None:
            lines.append(
                f"| {report.model} |  |  |  |  |  |  |  |  |  |  |  |  |  |"
            )
            continue
        dense = report.dense
        lines.append(
            "| "
            + " | ".join(
                [
                    report.model,
                    str(report.dimensions or ""),
                    _rate(dense.recall_at_5) if dense else "",
                    _rate(report.hybrid.recall_at_5),
                    _rate(dense.recall_at_8) if dense else "",
                    _rate(report.hybrid.recall_at_8),
                    _rate(dense.mrr) if dense else "",
                    _rate(report.hybrid.mrr),
                    _money(report.index_cost_usd),
                    _money(report.index_cost_this_run_usd),
                    _money(report.per_1k_queries_usd),
                    _ms(report.query_latency_p50_ms),
                    _ms(report.query_latency_p95_ms),
                    str(report.storage_float32_bytes or ""),
                ]
            )
            + " |"
        )
    lines.append("")
    for report in reports:
        lines.append(f"## {report.model}")
        lines.append("")
        if report.error:
            lines.append(f"Error: {report.error}")
            lines.append("")
            continue
        lines.append(
            f"Scored {report.question_count} questions "
            f"({report.draft_question_count} draft, "
            f"{report.existing_question_count} from the original six). "
            f"Unscored because no chunk label matched: {', '.join(report.unscored) or 'none'}."
        )
        if report.unmatched:
            joined = "; ".join(report.unmatched)
            lines.append(f"Expected sections with no chunk label: {joined}.")
        if report.draft_dense and report.draft_hybrid:
            lines.append(
                "Draft only. "
                f"Dense recall@5 {_rate(report.draft_dense.recall_at_5)}, "
                f"hybrid recall@5 {_rate(report.draft_hybrid.recall_at_5)}, "
                f"dense MRR {_rate(report.draft_dense.mrr)}, "
                f"hybrid MRR {_rate(report.draft_hybrid.mrr)}."
            )
        elif report.draft_hybrid:
            lines.append(
                "Draft only, strict. "
                f"Hybrid recall@5 {_rate(report.draft_hybrid.recall_at_5)}, "
                f"hybrid recall@8 {_rate(report.draft_hybrid.recall_at_8)}, "
                f"hybrid MRR {_rate(report.draft_hybrid.mrr)}."
            )
        if report.lenient_draft_hybrid:
            lines.append(
                "Draft only, lenient. "
                f"Hybrid recall@5 {_rate(report.lenient_draft_hybrid.recall_at_5)}, "
                f"hybrid recall@8 {_rate(report.lenient_draft_hybrid.recall_at_8)}, "
                f"hybrid MRR {_rate(report.lenient_draft_hybrid.mrr)}."
            )
        if report.hybrid is not None and (
            report.latency_scope == "hybrid_retrieve" or report.lenient_hybrid is not None
        ):
            lines.append(
                "All scored questions, strict. "
                f"Hybrid recall@5 {_rate(report.hybrid.recall_at_5)}, "
                f"hybrid recall@8 {_rate(report.hybrid.recall_at_8)}, "
                f"hybrid MRR {_rate(report.hybrid.mrr)}."
            )
        if report.lenient_hybrid is not None:
            lines.append(
                "All scored questions, lenient. "
                f"Hybrid recall@5 {_rate(report.lenient_hybrid.recall_at_5)}, "
                f"hybrid recall@8 {_rate(report.lenient_hybrid.recall_at_8)}, "
                f"hybrid MRR {_rate(report.lenient_hybrid.mrr)}."
            )
        if report.lenient_flips:
            lines.append("Questions that miss under strict and hit under lenient:")
            for item in report.lenient_flips:
                lines.append(f"- {item}")
        if report.miss_labels:
            lines.append("Hybrid misses at recall@5, top labels:")
            for item in report.miss_labels:
                lines.append(f"- {item}")
        lines.append(
            f"Price source {report.price_source}. "
            f"Index tokens {report.index_tokens}. "
            f"Tokens sent this run {report.index_tokens_this_run}. "
            f"Query tokens {report.query_tokens}. "
            f"Context length {report.context_length or 'not reported'}. "
            f"Cache file {report.cache_bytes} bytes."
        )
        lines.append(
            "Dense misses, first relevant chunk never appeared: "
            + (", ".join(report.misses) or "none")
            + "."
        )
        lines.append("")
    return "\n".join(lines)


def _latency_sentence(reports: list[ModelReport]) -> str:
    if any(report.latency_scope == "hybrid_retrieve" for report in reports):
        return (
            "Query latency times `hybrid_retrieve`: the query embedding plus both Postgres "
            "searches. The nearest-rank percentile uses `ceil`."
        )
    return (
        "Query latency is one pass over `embed_query` only. "
        "The nearest-rank percentile uses `ceil`."
    )


def _rate(value: float) -> str:
    return f"{value:.4f}"


def _money(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def _ms(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.3f}"


def write_reports(report_dir: Path, payload: dict[str, object], markdown: str) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "embed-bench.json"
    md_path = report_dir / "embed-bench.md"
    _replace(json_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    _replace(md_path, markdown)
    return json_path, md_path


def _replace(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def load_cba_chunks(pdf_path: Path) -> list[Chunk]:
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    corpus = load_corpus()
    offset = int(corpus["pdf_page_offset"])
    return chunk_cba_text(read_pdf_layout(pdf_path), source_url=pdf_url(), page_offset=offset)


def check_questions(chunks: list[Chunk], questions: list[BenchQuestion]) -> list[str]:
    problems: list[str] = []
    for question in questions:
        if not question.draft:
            continue
        found = matching_chunks(chunks, question)
        if not found:
            problems.append(f"UNMATCHED {question.id}")
            continue
        print(f"ok {question.id} chunks={len(found)} section={found[0].section[:80]}")
    return problems


def _model_list(raw: str) -> list[str]:
    models: list[str] = []
    for item in raw.split(","):
        name = item.strip()
        if name and name not in models:
            models.append(name)
    if HASH_MODEL not in models:
        models.insert(0, HASH_MODEL)
    return models


def passage_snippet(text: str, limit: int = 100) -> str:
    """Show the passage, skipping the article and section breadcrumb."""
    body = text
    head, separator, rest = text.partition("\n\n")
    if separator and "\nSection " in head and head.startswith(("Article ", "Exhibit ")):
        body = rest
    return " ".join(body.split())[:limit]


def _display_label(section: str) -> str:
    label = " ".join(section.split())
    if len(label) > 120:
        return label[:117] + "..."
    return label


def hybrid_miss_labels(
    questions: list[BenchQuestion],
    rankings: dict[str, list[Chunk]],
) -> list[str]:
    lines: list[str] = []
    for question in questions:
        ranked = rankings.get(question.id, [])
        if recall_at(ranked, question, 5) >= 1:
            continue
        labels: list[str] = []
        for chunk in ranked[:5]:
            snippet = passage_snippet(chunk.text, 80)
            label = _display_label(chunk.section)
            if snippet:
                label = f"{label} :: {snippet}"
            labels.append(label)
        shown = " | ".join(labels) if labels else "(no rows)"
        lines.append(f"{question.id}: {shown}")
    return lines


def lenient_flip_lines(
    questions: list[BenchQuestion],
    rankings: dict[str, list[Chunk]],
) -> list[str]:
    lines: list[str] = []
    for question in questions:
        ranked = rankings.get(question.id, [])
        strict = recall_at(ranked, question, 5)
        loose = recall_at(ranked, question, 5, matches=lenient_chunk_matches)
        if strict >= 1 or loose < 1 or not ranked:
            continue
        top = ranked[0]
        label = _display_label(top.section)
        snippet = passage_snippet(top.text)
        lines.append(f"{question.id}: {label} | {snippet}")
    return lines


def database_block_reason(settings: Settings) -> str | None:
    if not settings.database_url.strip():
        return DATABASE_URL_REQUIRED
    provider = settings.resolved_embedding_provider
    if provider == "openrouter":
        if not settings.embedding_model.strip():
            return (
                "EMBEDDING_MODEL is required when EMBEDDING_PROVIDER is openrouter. "
                "No connection was opened."
            )
        if not settings.openrouter_api_key.strip():
            return KEY_REQUIRED
        return None
    if provider == "openai" and not settings.openai_api_key.strip():
        return "OPENAI_API_KEY is required to embed the query. No connection was opened."
    if provider not in {"hash", "openai", "openrouter"}:
        return "EMBEDDING_PROVIDER must be hash, openai, or openrouter. No connection was opened."
    return None


def known_source_urls() -> set[str]:
    urls = {pdf_url()}
    manifest = PDF_PATH.parent / "manifest.json"
    if not manifest.is_file():
        return urls
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("url"), str):
        url = payload["url"].strip()
        if url:
            urls.add(url)
    return urls


def pick_source_document(rows: list[tuple[object, str]], known_urls: set[str]) -> object:
    if not rows:
        raise RuntimeError("No source_documents row. No chunks were read.")
    if len(rows) == 1:
        return rows[0][0]
    for document_id, url in rows:
        if url in known_urls:
            return document_id
    raise RuntimeError(
        "More than one source document is stored, and none match the corpus URL. "
        "No chunks were scored."
    )


def chunk_from_row(row: object) -> Chunk:
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


def rank_with_hybrid(
    store: ChunkStore,
    embedder: Embedder,
    questions: list[BenchQuestion],
    *,
    candidate_k: int,
    rrf_k: int,
    top_k: int,
) -> tuple[dict[str, list[Chunk]], list[float]]:
    rankings: dict[str, list[Chunk]] = {}
    latencies: list[float] = []
    for question in questions:
        started = time.perf_counter()
        ranked = hybrid_retrieve(
            store,
            question.question,
            embedder,
            candidate_k=candidate_k,
            top_k=top_k,
            rrf_k=rrf_k,
        )
        latencies.append((time.perf_counter() - started) * 1000)
        rankings[question.id] = ranked
    return rankings, latencies


def open_database(settings: Settings):
    from app.database.models import CbaChunk, SourceDocument
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.sqlalchemy_database_url)
    session = sessionmaker(bind=engine)()
    try:
        documents = session.execute(select(SourceDocument.id, SourceDocument.source_url)).all()
        document_id = pick_source_document(
            [(row.id, row.source_url) for row in documents],
            known_source_urls(),
        )
        rows = session.execute(
            select(CbaChunk)
            .where(CbaChunk.document_id == document_id)
            .order_by(CbaChunk.chunk_index)
        ).scalars()
        chunks = [chunk_from_row(row) for row in rows]
        store = PostgresChunkStore(session, {chunk.id: chunk for chunk in chunks})
        return session, store, chunks, engine
    except Exception:
        session.close()
        engine.dispose()
        raise


def _database_report(
    settings: Settings,
    chunks: list[Chunk],
    questions: list[BenchQuestion],
    skipped: list[str],
    rankings: dict[str, list[Chunk]],
    latencies: list[float],
    query_tokens: int,
) -> ModelReport:
    draft = [question for question in questions if question.draft]
    existing = [question for question in questions if not question.draft]
    provider = settings.resolved_embedding_provider
    model = HASH_MODEL if provider == "hash" else settings.resolved_embedding_model
    dimensions = settings.resolved_embedding_dimensions
    return ModelReport(
        model=model,
        dimensions=dimensions,
        chunk_count=len(chunks),
        question_count=len(questions),
        draft_question_count=len(draft),
        existing_question_count=len(existing),
        unscored=[],
        unmatched=_unmatched(chunks, questions),
        skipped=skipped,
        dense=None,
        hybrid=aggregate(questions, rankings),
        draft_dense=None,
        draft_hybrid=aggregate(draft, rankings) if draft else None,
        existing_dense=None,
        existing_hybrid=aggregate(existing, rankings) if existing else None,
        index_tokens=0,
        index_tokens_this_run=0,
        query_tokens=query_tokens,
        price_per_million=None,
        price_source="not priced",
        index_cost_usd=None,
        index_cost_this_run_usd=None,
        per_1k_queries_usd=None,
        query_latency_p50_ms=percentile(latencies, 50) if latencies else None,
        query_latency_p95_ms=percentile(latencies, 95) if latencies else None,
        query_count=len(latencies),
        context_length=None,
        storage_float32_bytes=len(chunks) * dimensions * 4,
        cache_bytes=0,
        misses=[],
        miss_labels=hybrid_miss_labels(questions, rankings),
        latency_scope="hybrid_retrieve",
        lenient_hybrid=aggregate(questions, rankings, matches=lenient_chunk_matches),
        lenient_draft_hybrid=(
            aggregate(draft, rankings, matches=lenient_chunk_matches) if draft else None
        ),
        lenient_flips=lenient_flip_lines(questions, rankings),
    )


def _print_metrics(kind: str, metrics: RankMetrics) -> None:
    print(
        f"{kind} "
        f"R@5 {_rate(metrics.recall_at_5)} "
        f"R@8 {_rate(metrics.recall_at_8)} "
        f"MRR {_rate(metrics.mrr)}"
    )


def _print_database_summary(report: ModelReport) -> None:
    if report.draft_hybrid is not None:
        _print_metrics("strict draft", report.draft_hybrid)
    if report.lenient_draft_hybrid is not None:
        _print_metrics("lenient draft", report.lenient_draft_hybrid)
    if report.hybrid is not None:
        _print_metrics("strict all", report.hybrid)
    if report.lenient_hybrid is not None:
        _print_metrics("lenient all", report.lenient_hybrid)
    print(f"query p95 {_ms(report.query_latency_p95_ms)} ms (hybrid_retrieve)")
    if report.lenient_flips:
        print("lenient flips:")
        for line in report.lenient_flips:
            print(line)
    if report.miss_labels:
        print("strict misses at R@5:")
        for line in report.miss_labels:
            print(line)


def _run_database(
    settings: Settings,
    question_paths: list[Path] | None,
    report_dir: Path,
) -> int:
    reason = database_block_reason(settings)
    if reason is not None:
        print(reason, file=sys.stderr)
        return 2
    questions, skipped = load_bench_questions(question_paths or [QUESTIONS_PATH, DRAFT_PATH])
    try:
        embedder = build_embedder(settings)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    opened = None
    try:
        opened = open_database(settings)
        _session, store, chunks, _engine = opened
        before = int(getattr(embedder, "prompt_tokens", 0))
        top_k = max(settings.retrieval_candidate_k, settings.retrieval_top_k, 8)
        rankings, latencies = rank_with_hybrid(
            store,
            embedder,
            questions,
            candidate_k=settings.retrieval_candidate_k,
            rrf_k=settings.retrieval_rrf_k,
            top_k=top_k,
        )
        query_tokens = int(getattr(embedder, "prompt_tokens", 0)) - before
        report = _database_report(
            settings,
            chunks,
            questions,
            skipped,
            rankings,
            latencies,
            query_tokens,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if opened is not None:
            opened[0].close()
            opened[3].dispose()
        close = getattr(embedder, "close", None)
        if callable(close):
            close()
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "generated_at": generated_at,
        "price_fetch": "skipped",
        "candidate_k": settings.retrieval_candidate_k,
        "rrf_k": settings.retrieval_rrf_k,
        "embedding_dimensions_constant": EMBEDDING_DIMENSIONS,
        "latency_scope": "hybrid_retrieve",
        "models": [_report_dict(report)],
    }
    markdown = render_markdown(reports=[report], price_fetch="skipped", generated_at=generated_at)
    json_path, md_path = write_reports(report_dir, payload, markdown)
    _print_database_summary(report)
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    return 1 if report.error else 0


def main(
    argv: list[str] | None = None,
    *,
    corpus: list[Chunk] | None = None,
    settings: Settings | None = None,
    fetch_catalog=None,
    embedder_for_model=None,
) -> int:
    parser = argparse.ArgumentParser(description="Compare embedders on CBA retrieval.")
    parser.add_argument(
        "--models",
        default=HASH_MODEL,
        help=(
            "Comma-separated model ids. hash always runs. "
            "Example: qwen/qwen3-embedding-8b,mongodb/voyage-4-lite"
        ),
    )
    parser.add_argument("--live", action="store_true", help="Allow OpenRouter embedding calls.")
    parser.add_argument(
        "--database",
        action="store_true",
        help=(
            "Score hybrid_retrieve against DATABASE_URL through PostgresChunkStore. "
            "Does not connect unless this flag is set. "
            "Requires the embedding key for the configured provider."
        ),
    )
    parser.add_argument("--pdf", type=Path, default=PDF_PATH)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--questions", action="append", type=Path)
    parser.add_argument(
        "--check-questions",
        action="store_true",
        help="Check draft section labels against the corpus and do not embed.",
    )
    args = parser.parse_args(argv)
    loaded_settings = settings if settings is not None else Settings()
    if args.database:
        return _run_database(loaded_settings, args.questions, args.report_dir)
    models = _model_list(args.models)
    remote = [model for model in models if model != HASH_MODEL]
    if remote and not args.live and not args.check_questions:
        print(LIVE_REQUIRED, file=sys.stderr)
        return 2
    missing_key = remote and args.live and not args.check_questions
    if missing_key and not loaded_settings.openrouter_api_key.strip():
        print(KEY_REQUIRED, file=sys.stderr)
        return 2
    try:
        chunks = corpus if corpus is not None else load_cba_chunks(args.pdf)
    except FileNotFoundError:
        print(
            "The CBA PDF is not on disk. Run `python data/download_cba.py` from the repo root. "
            "The file stays gitignored.",
            file=sys.stderr,
        )
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    question_paths = args.questions or [QUESTIONS_PATH, DRAFT_PATH]
    questions, skipped = load_bench_questions(question_paths)
    if args.check_questions:
        problems = check_questions(chunks, questions)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    catalog: dict[str, CatalogEntry] = {}
    price_fetch = "skipped"
    if remote:
        fetch = fetch_catalog or fetch_model_catalog
        try:
            catalog = fetch()
            price_fetch = "ok"
        except (OSError, httpx.HTTPError, ValueError):
            price_fetch = "fallback"
    reports: list[ModelReport] = []
    for model in models:
        price, source, context = resolve_price(model, catalog)
        if model == HASH_MODEL:
            embedder: PricedEmbedder = _HashUsage(loaded_settings.openai_embedding_dimensions)
            hint = loaded_settings.openai_embedding_dimensions
        else:
            hint = None
            if embedder_for_model is not None:
                embedder = embedder_for_model(model)
            else:
                embedder = OpenRouterEmbedder(
                    Settings(
                        embedding_provider="openrouter",
                        embedding_model=model,
                        embedding_dimensions=None,
                        openrouter_api_key=loaded_settings.openrouter_api_key,
                    )
                )
        try:
            reports.append(
                score_model(
                    model=model,
                    embedder=embedder,
                    chunks=chunks,
                    questions=questions,
                    skipped=skipped,
                    cache_path=_cache_path(args.report_dir, model),
                    candidate_k=loaded_settings.retrieval_candidate_k,
                    rrf_k=loaded_settings.retrieval_rrf_k,
                    price_per_million=price,
                    price_source=source,
                    context_length=context,
                    dimensions_hint=hint,
                )
            )
        finally:
            close = getattr(embedder, "close", None)
            if callable(close):
                close()
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "generated_at": generated_at,
        "price_fetch": price_fetch,
        "candidate_k": loaded_settings.retrieval_candidate_k,
        "rrf_k": loaded_settings.retrieval_rrf_k,
        "embedding_dimensions_constant": EMBEDDING_DIMENSIONS,
        "models": [_report_dict(report) for report in reports],
    }
    markdown = render_markdown(reports, price_fetch=price_fetch, generated_at=generated_at)
    json_path, md_path = write_reports(args.report_dir, payload, markdown)
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    if any(report.error for report in reports):
        return 1
    return 0


def _report_dict(report: ModelReport) -> dict[str, object]:
    payload = asdict(report)
    return payload


class _HashUsage(HashEmbedder):
    model = HASH_MODEL

    def __init__(self, dimensions: int) -> None:
        super().__init__(dimensions=dimensions)
        self.prompt_tokens = 0
        self.total_tokens = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


if __name__ == "__main__":
    raise SystemExit(main())

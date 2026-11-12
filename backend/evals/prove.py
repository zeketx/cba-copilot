from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import BaseModel, Field, model_validator

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from app.assistant.drafter import (  # noqa: E402
    Drafter,
    OverlapDrafter,
    build_live_drafter,
)
from app.config import Settings, require_live_settings  # noqa: E402
from app.demo import demo_embedder, demo_store  # noqa: E402
from app.domain import (  # noqa: E402
    Chunk,
    Claim,
    CopilotResponse,
    DraftAnswer,
    DraftClaim,
    Refusal,
)
from app.grounding.validate import normalize_space  # noqa: E402
from app.pipeline import answer_question  # noqa: E402
from app.retrieval.embed import Embedder, build_embedder  # noqa: E402
from app.retrieval.hybrid import hybrid_retrieve  # noqa: E402
from app.retrieval.store import ChunkStore  # noqa: E402

from evals.metrics import ExpectedSection, chunk_matches  # noqa: E402

CASES_PATH = Path(__file__).with_name("corpus_cases.yaml")
_BACKEND = Path(__file__).resolve().parent.parent
_ROOT = _BACKEND.parent
LIVE_RUNS = _ROOT / "docs" / "phase10" / "runs"

CaseKind = Literal[
    "whole_rule",
    "exception",
    "cross_reference",
    "two_passages",
    "season_or_date",
    "computation",
    "missing_inputs",
    "definition",
    "no_evidence",
    "ambiguous",
    "bad_citation",
]

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


class ExpectedSectionSpec(BaseModel):
    article: int
    section_contains: str
    page_start: int | None = None
    page_end: int | None = None
    note: str = ""

    def as_expected(self) -> ExpectedSection:
        return ExpectedSection(article=self.article, section_contains=self.section_contains)


class CorpusCase(BaseModel):
    id: str
    kind: CaseKind
    question: str
    expected_sections: list[ExpectedSectionSpec] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)
    expected_number: float | None = None
    injected_text: str = ""
    injected_quote: str = ""

    @model_validator(mode="after")
    def kind_fields(self) -> CorpusCase:
        if self.kind == "computation" and self.expected_number is None:
            raise ValueError("computation cases need expected_number")
        if self.kind == "exception" and not self.required_phrases:
            raise ValueError("exception cases need required_phrases")
        if self.kind == "bad_citation" and (
            not self.injected_text.strip() or not self.injected_quote.strip()
        ):
            raise ValueError("bad_citation cases need injected_text and injected_quote")
        return self


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GradeContext:
    passages: list[Chunk]

    def by_id(self) -> dict[str, Chunk]:
        return {passage.id: passage for passage in self.passages}


@dataclass(frozen=True)
class CaseResult:
    case: CorpusCase
    response: CopilotResponse
    retrieved_ids: list[str]
    verdict: Verdict

    def as_json(self) -> dict[str, object]:
        return {
            "id": self.case.id,
            "kind": self.case.kind,
            "question": self.case.question,
            "response": self.response.model_dump(mode="json"),
            "retrieved_ids": self.retrieved_ids,
            "verdict": "pass" if self.verdict.passed else "fail",
            "reasons": list(self.verdict.reasons),
        }


Grader = Callable[[CorpusCase, CopilotResponse, GradeContext], Verdict]


def load_cases(path: Path = CASES_PATH) -> list[CorpusCase]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("corpus_cases.yaml must be a list")
    cases = [CorpusCase.model_validate(item) for item in loaded]
    kinds = [case.kind for case in cases]
    if len(cases) != len(get_args(CaseKind)) or set(kinds) != set(get_args(CaseKind)):
        raise ValueError("corpus_cases.yaml must contain one case per phase 10 rule")
    return cases


def parse_numbers(text: str) -> set[float]:
    found: set[float] = set()
    for match in _NUMBER.finditer(text):
        found.add(float(match.group().replace(",", "")))
    return found


def has_number(text: str, expected: float) -> bool:
    return any(abs(value - expected) < 1e-6 for value in parse_numbers(text))


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return str(value)


def response_claims(response: CopilotResponse) -> list[Claim]:
    if isinstance(response, Refusal):
        return []
    return list(response.claims)


def response_blob(response: CopilotResponse) -> str:
    parts = [getattr(response, "message", "") or ""]
    parts.extend(claim.text for claim in response_claims(response))
    return normalize_space(" ".join(parts))


def chunks_for_claim(claim: Claim, ctx: GradeContext) -> list[Chunk]:
    by_id = ctx.by_id()
    found: list[Chunk] = []
    for passage_id in claim.passage_ids:
        chunk = by_id.get(passage_id)
        if chunk is not None:
            found.append(chunk)
    return found


def cited_chunks(response: CopilotResponse, ctx: GradeContext) -> list[Chunk]:
    found: list[Chunk] = []
    for claim in response_claims(response):
        found.extend(chunks_for_claim(claim, ctx))
    return found


def cites_expected(response: CopilotResponse, ctx: GradeContext, spec: ExpectedSectionSpec) -> bool:
    expected = spec.as_expected()
    return any(chunk_matches(chunk, expected) for chunk in cited_chunks(response, ctx))


def missing_sections(
    response: CopilotResponse,
    ctx: GradeContext,
    specs: list[ExpectedSectionSpec],
) -> list[str]:
    missing: list[str] = []
    for spec in specs:
        if not cites_expected(response, ctx, spec):
            missing.append(f"missing article {spec.article} section {spec.section_contains}")
    return missing


def claim_supported(claim: Claim, ctx: GradeContext) -> bool:
    needle = normalize_space(claim.text)
    if not needle:
        return False
    return any(needle in normalize_space(chunk.text) for chunk in chunks_for_claim(claim, ctx))


def extra_numbers(response: CopilotResponse, ctx: GradeContext) -> set[float]:
    quoted: set[float] = set()
    for chunk in cited_chunks(response, ctx):
        quoted |= parse_numbers(chunk.text)
    return parse_numbers(response_blob(response)) - quoted


def _ok() -> Verdict:
    return Verdict(passed=True, reasons=())


def _fail(*reasons: str) -> Verdict:
    return Verdict(passed=False, reasons=reasons)


def _unsupported(response: CopilotResponse, ctx: GradeContext) -> str | None:
    if any(not claim_supported(claim, ctx) for claim in response_claims(response)):
        return "claim text is not in a cited passage"
    return None


def _grade_whole_rule(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    if response.kind != "answer":
        return _fail(f"expected answer, got {response.kind}")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    unsupported = _unsupported(response, ctx)
    if unsupported:
        return _fail(unsupported)
    for claim in response.claims:
        cited = chunks_for_claim(claim, ctx)
        if not any(
            chunk_matches(chunk, spec.as_expected())
            for spec in case.expected_sections
            for chunk in cited
        ):
            return _fail("a claim did not cite the expected section")
    return _ok()


def _grade_exception(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    if response.kind != "answer":
        return _fail(f"expected answer, got {response.kind}")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    unsupported = _unsupported(response, ctx)
    if unsupported:
        return _fail(unsupported)
    blob = response_blob(response).lower()
    absent = [phrase for phrase in case.required_phrases if phrase.lower() not in blob]
    if absent:
        return _fail(f"missing required phrases: {', '.join(absent)}")
    return _ok()


def _grade_cross_reference(
    case: CorpusCase, response: CopilotResponse, ctx: GradeContext
) -> Verdict:
    if response.kind != "answer":
        return _fail(f"expected answer, got {response.kind}")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    unsupported = _unsupported(response, ctx)
    if unsupported:
        return _fail(unsupported)
    return _ok()


def _grade_two_passages(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    if response.kind == "refusal":
        return _ok()
    if response.kind != "answer":
        return _fail(f"expected answer or refusal, got {response.kind}")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    unsupported = _unsupported(response, ctx)
    if unsupported:
        return _fail(unsupported)
    return _ok()


def _grade_season_or_date(
    case: CorpusCase, response: CopilotResponse, ctx: GradeContext
) -> Verdict:
    if response.kind == "clarification" and response.reason == "ambiguous":
        return _ok()
    if response.kind != "answer":
        return _fail("expected the cited passage or a question about the date")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    return _ok()


def _grade_computation(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    if response.kind != "answer":
        return _fail(f"expected answer, got {response.kind}")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    assert case.expected_number is not None
    blob = " ".join(claim.text for claim in response.claims)
    if not has_number(blob, case.expected_number):
        return _fail(f"claim text lacks {format_number(case.expected_number)}")
    return _ok()


def _grade_missing_inputs(
    case: CorpusCase, response: CopilotResponse, ctx: GradeContext
) -> Verdict:
    if response.kind != "clarification" or response.reason != "missing_inputs":
        return _fail("expected missing_inputs")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    extra = extra_numbers(response, ctx)
    if extra:
        return _fail("response adds a number the quote does not contain")
    return _ok()


def _grade_definition(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    if response.kind != "answer":
        return _fail(f"expected answer, got {response.kind}")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    unsupported = _unsupported(response, ctx)
    if unsupported:
        return _fail(unsupported)
    extra = extra_numbers(response, ctx)
    if extra:
        return _fail("response adds a number the quote does not contain")
    return _ok()


def _grade_no_evidence(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    del case, ctx
    if response.kind != "refusal" or response.reason != "no_evidence":
        return _fail("expected no_evidence")
    if response_claims(response):
        return _fail("no_evidence response carried a claim")
    return _ok()


def _grade_ambiguous(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    if response.kind != "clarification" or response.reason != "ambiguous":
        return _fail("expected ambiguous")
    missing = missing_sections(response, ctx, case.expected_sections)
    if missing:
        return _fail(*missing)
    return _ok()


def _grade_bad_citation(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    del ctx
    texts = [claim.text for claim in response_claims(response)]
    if case.injected_text in texts:
        return _fail("injected claim was kept")
    return _ok()


GRADERS: dict[CaseKind, Grader] = {
    "whole_rule": _grade_whole_rule,
    "exception": _grade_exception,
    "cross_reference": _grade_cross_reference,
    "two_passages": _grade_two_passages,
    "season_or_date": _grade_season_or_date,
    "computation": _grade_computation,
    "missing_inputs": _grade_missing_inputs,
    "definition": _grade_definition,
    "no_evidence": _grade_no_evidence,
    "ambiguous": _grade_ambiguous,
    "bad_citation": _grade_bad_citation,
}

if set(GRADERS) != set(get_args(CaseKind)):
    raise RuntimeError("GRADERS must cover every CaseKind")


class InjectedClaimDrafter:
    def __init__(self, inner: Drafter, text: str, quote: str) -> None:
        self._inner = inner
        self._text = text
        self._quote = quote

    def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer:
        draft = self._inner.draft(question, passages)
        target = next(
            (
                passage
                for passage in passages
                if normalize_space(self._quote) not in normalize_space(passage.text)
            ),
            passages[0] if passages else None,
        )
        if target is None:
            return draft
        injected = DraftClaim(
            text=self._text,
            quote=self._quote,
            passage_ids=[target.id],
        )
        return draft.model_copy(update={"claims": [*draft.claims, injected]})


def grade_case(case: CorpusCase, response: CopilotResponse, ctx: GradeContext) -> Verdict:
    return GRADERS[case.kind](case, response, ctx)


def missing_live_settings(settings: Settings) -> str | None:
    try:
        require_live_settings(settings)
    except (RuntimeError, ValueError) as exc:
        return str(exc)
    provider = settings.resolved_embedding_provider
    if provider == "openrouter" and not settings.openrouter_api_key.strip():
        return "OPENROUTER_API_KEY is required when EMBEDDING_PROVIDER is openrouter"
    if provider == "openai" and not settings.openai_api_key.strip():
        return "OPENAI_API_KEY is required when EMBEDDING_PROVIDER is openai"
    return None


def _answer_kwargs(settings: Settings) -> dict[str, int]:
    return {
        "candidate_k": settings.retrieval_candidate_k,
        "top_k": settings.retrieval_top_k,
        "rrf_k": settings.retrieval_rrf_k,
        "context_per_hit": settings.retrieval_context_per_hit,
        "context_max": settings.retrieval_context_max,
    }


def run_case(
    case: CorpusCase,
    store: ChunkStore,
    embedder: Embedder,
    drafter: Drafter,
    settings: Settings,
) -> CaseResult:
    kwargs = _answer_kwargs(settings)
    retrieved = hybrid_retrieve(store, case.question, embedder, **kwargs)
    used: Drafter = drafter
    if case.kind == "bad_citation":
        used = InjectedClaimDrafter(drafter, case.injected_text, case.injected_quote)
    response = answer_question(case.question, store, embedder, used, **kwargs)
    ctx = GradeContext(passages=retrieved.passages())
    return CaseResult(
        case=case,
        response=response,
        retrieved_ids=[chunk.id for chunk in retrieved.passages()],
        verdict=grade_case(case, response, ctx),
    )


def summary_markdown(results: list[CaseResult]) -> str:
    lines = ["| case | result | reason |", "| --- | --- | --- |"]
    for row in results:
        result = "pass" if row.verdict.passed else "fail"
        reason = "; ".join(row.verdict.reasons).replace("|", "/")
        lines.append(f"| {row.case.id} | {result} | {reason} |")
    return "\n".join(lines) + "\n"


def write_run(directory: Path, results: list[CaseResult], *, live: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"live": live, "cases": [row.as_json() for row in results]}
    (directory / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "summary.md").write_text(summary_markdown(results), encoding="utf-8")


def run_suite(
    cases: list[CorpusCase],
    store: ChunkStore,
    embedder: Embedder,
    drafter: Drafter,
    settings: Settings,
) -> list[CaseResult]:
    return [run_case(case, store, embedder, drafter, settings) for case in cases]


def _live_output_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return LIVE_RUNS / stamp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove every phase 10 corpus rule.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query the live store, live embedder, and live drafter.",
    )
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.live:
        settings = Settings()
        missing = missing_live_settings(settings)
        if missing is not None:
            print(missing, file=sys.stderr)
            return 2
        from evals.embed_bench import open_database

        session, store, _chunks, engine = open_database(settings)
        try:
            embedder = build_embedder(settings)
            drafter = build_live_drafter(settings)
            results = run_suite(cases, store, embedder, drafter, settings)
        finally:
            session.close()
            engine.dispose()
        output = _live_output_dir()
        write_run(output, results, live=True)
        print(output)
        return 0 if all(row.verdict.passed for row in results) else 1
    settings = Settings(_env_file=None)
    store = demo_store(settings.resolved_embedding_dimensions)
    embedder = demo_embedder(settings.resolved_embedding_dimensions)
    results = run_suite(cases, store, embedder, OverlapDrafter(), settings)
    output = Path(tempfile.mkdtemp(prefix="phase10-"))
    write_run(output, results, live=False)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

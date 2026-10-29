
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from app.assistant.drafter import OverlapDrafter  # noqa: E402
from app.config import Settings  # noqa: E402
from app.demo import demo_embedder, demo_store, load_demo_chunks  # noqa: E402
from app.domain import CitedAnswer  # noqa: E402
from app.pipeline import answer_question  # noqa: E402
from app.retrieval.hybrid import hybrid_retrieve  # noqa: E402

QUESTIONS_PATH = Path(__file__).with_name("questions.yaml")

LIVE_DISABLED = (
    "Live models are disabled in this skeleton. "
    "The flag is reserved for a later run after the owner adds credits."
)

def load_questions() -> list[dict[str, object]]:
    loaded = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or len(loaded) != 6:
        raise ValueError("the harness must contain six questions")
    return loaded

def _cited_sections(response: CitedAnswer) -> list[tuple[int | None, str]]:
    by_id = {chunk.id: chunk for chunk in load_demo_chunks()}
    found: list[tuple[int | None, str]] = []
    for claim in response.claims:
        if not claim.passage_ids:
            continue
        for passage_id in claim.passage_ids:
            chunk = by_id[passage_id]
            found.append((chunk.article_number, chunk.section))
    return found

def evaluate(
    question: dict[str, object],
    response: object,
    *,
    retrieved_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    expect = question["expect"]
    qid = question["id"]
    if expect == "refusal":
        if getattr(response, "kind", None) != "refusal":
            errors.append(f"{qid}: expected a refusal")
        return errors
    if getattr(response, "kind", None) != "answer":
        errors.append(f"{qid}: expected a cited answer, got {getattr(response, 'kind', None)}")
        return errors
    assert isinstance(response, CitedAnswer)
    if not response.claims:
        errors.append(f"{qid}: answer has no claims")
        return errors
    cited = _cited_sections(response)
    if not cited:
        errors.append(f"{qid}: answer has no citations")
    articles = question["articles"]
    assert isinstance(articles, list)
    hits = []
    for expected in articles:
        assert isinstance(expected, dict)
        matched = any(
            article == expected["article"] and str(expected["section_contains"]) in section
            for article, section in cited
        )
        hits.append(matched)
        if not matched and question["match"] == "all":
            article = expected["article"]
            section = expected["section_contains"]
            errors.append(f"{qid}: missing article {article} section {section}")
    if question["match"] == "any" and hits and not any(hits):
        errors.append(f"{qid}: none of the expected articles were cited")
    for claim in response.claims:
        for passage_id in claim.passage_ids:
            if passage_id not in retrieved_ids:
                errors.append(f"{qid}: citation {passage_id} was not in the retrieved set")
    return errors

def run_suite() -> list[str]:
    settings = Settings()
    store = demo_store(settings.openai_embedding_dimensions)
    embedder = demo_embedder(settings.openai_embedding_dimensions)
    drafter = OverlapDrafter()
    errors: list[str] = []
    for question in load_questions():
        asked = str(question["question"])
        retrieved = hybrid_retrieve(
            store,
            asked,
            embedder,
            candidate_k=settings.retrieval_candidate_k,
            top_k=settings.retrieval_top_k,
            rrf_k=settings.retrieval_rrf_k,
        )
        response = answer_question(
            asked,
            store,
            embedder,
            drafter,
            candidate_k=settings.retrieval_candidate_k,
            top_k=settings.retrieval_top_k,
            rrf_k=settings.retrieval_rrf_k,
        )
        errors.extend(evaluate(question, response, retrieved_ids={item.id for item in retrieved}))
    return errors

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CBA copilot question harness.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Reserved for live models. This skeleton exits before any API call.",
    )
    args = parser.parse_args(argv)
    if args.live:
        print(LIVE_DISABLED, file=sys.stderr)
        return 2
    errors = run_suite()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"passed {len(load_questions())} questions on stand-in models")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

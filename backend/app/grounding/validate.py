from __future__ import annotations

import re

from app.domain import (
    CITATIONS_DROPPED_MESSAGE,
    NO_EVIDENCE_MESSAGE,
    Ambiguous,
    Chunk,
    CitedAnswer,
    CopilotResponse,
    DraftAnswer,
    MissingInputs,
    Refusal,
)

_DIGITS = re.compile(r"\d+")


def unquoted_digit_runs(text: str, quotes: list[str]) -> set[str]:
    """Return digit runs in text that none of the quotes contain.

    A run is a maximal sequence of digits. The check misses a number spelled
    in words. It allows a run the quote already contains, including a run the
    model reused as a result. It does not parse arithmetic, units, or rounding.
    """
    allowed: set[str] = set()
    for quote in quotes:
        allowed.update(_DIGITS.findall(quote))
    return set(_DIGITS.findall(text)) - allowed


def _only_questions(text: str) -> bool:
    stripped = text.strip()
    if "?" not in stripped:
        return False
    _, _, tail = stripped.rpartition("?")
    if tail.strip(" \t\"')"):
        return False
    parts = [part.strip() for part in re.split(r"[.!]+", stripped) if part.strip()]
    return bool(parts) and all("?" in part for part in parts)


def _require_retrieved(
    passage_ids: list[str],
    allowed: set[str],
    *,
    minimum: int,
) -> list[str] | None:
    if len(passage_ids) < minimum:
        return None
    seen: list[str] = []
    for passage_id in passage_ids:
        if passage_id not in allowed:
            return None
        if passage_id not in seen:
            seen.append(passage_id)
    if len(seen) < minimum:
        return None
    return seen


def _no_evidence() -> Refusal:
    return Refusal(reason="no_evidence", message=NO_EVIDENCE_MESSAGE)


def _ambiguous(draft: DraftAnswer, passages: list[Chunk]) -> Ambiguous | Refusal:
    passage_ids = _require_retrieved(
        draft.passage_ids,
        {passage.id for passage in passages},
        minimum=2,
    )
    if passage_ids is None or not _only_questions(draft.question):
        return _no_evidence()
    return Ambiguous(question=draft.question.strip(), passage_ids=passage_ids)


def _missing_inputs(draft: DraftAnswer, passages: list[Chunk]) -> MissingInputs | Refusal:
    allowed = {passage.id for passage in passages}
    passage_ids = _require_retrieved(draft.passage_ids, allowed, minimum=1)
    text = draft.text.strip()
    if passage_ids is None or not text:
        return _no_evidence()
    quotes = [passage.text for passage in passages if passage.id in passage_ids]
    if unquoted_digit_runs(text, quotes):
        return _no_evidence()
    return MissingInputs(text=text, passage_ids=passage_ids)


def validate_draft(draft: DraftAnswer, passages: list[Chunk]) -> CopilotResponse:
    if draft.kind == "ambiguous":
        return _ambiguous(draft, passages)
    if draft.kind == "missing_inputs":
        return _missing_inputs(draft, passages)
    if draft.insufficient_evidence or not draft.claims:
        return _no_evidence()

    allowed = {passage.id for passage in passages}
    kept = [
        claim
        for claim in draft.claims
        if claim.passage_ids and all(passage_id in allowed for passage_id in claim.passage_ids)
    ]
    if not kept:
        return Refusal(reason="citations_dropped", message=CITATIONS_DROPPED_MESSAGE)
    return CitedAnswer(claims=kept)

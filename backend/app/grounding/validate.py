
from __future__ import annotations

from collections.abc import Callable

from app.domain import (
    AMBIGUOUS_MESSAGE,
    CITATIONS_DROPPED_MESSAGE,
    NO_EVIDENCE_MESSAGE,
    Chunk,
    CitedAnswer,
    Claim,
    Clarification,
    CopilotResponse,
    DraftAnswer,
    DraftStatus,
    Refusal,
)


def _kept_claims(draft: DraftAnswer, passages: list[Chunk]) -> list[Claim]:
    allowed = {passage.id for passage in passages}
    return [
        claim
        for claim in draft.claims
        if claim.passage_ids and all(passage_id in allowed for passage_id in claim.passage_ids)
    ]


def _no_evidence(_draft: DraftAnswer, _kept: list[Claim]) -> Refusal:
    return Refusal(reason="no_evidence", message=NO_EVIDENCE_MESSAGE)


def _citations_dropped() -> Refusal:
    return Refusal(reason="citations_dropped", message=CITATIONS_DROPPED_MESSAGE)


def _as_answer(draft: DraftAnswer, kept: list[Claim]) -> CopilotResponse:
    if not draft.claims:
        return _no_evidence(draft, kept)
    if not kept:
        return _citations_dropped()
    return CitedAnswer(claims=kept)


def _as_ambiguous(_draft: DraftAnswer, kept: list[Claim]) -> CopilotResponse:
    cited = {passage_id for claim in kept for passage_id in claim.passage_ids}
    if len(cited) < 2:
        return _citations_dropped()
    return Clarification(reason="ambiguous", message=AMBIGUOUS_MESSAGE, claims=kept)


def _as_missing_inputs(draft: DraftAnswer, kept: list[Claim]) -> CopilotResponse:
    names = [name.strip() for name in draft.missing_inputs if name.strip()]
    if not names:
        return _no_evidence(draft, kept)
    if not kept:
        return _citations_dropped()
    message = (
        "The cited passage needs inputs the question does not give: "
        f"{', '.join(names)}. Add them and ask again."
    )
    return Clarification(reason="missing_inputs", message=message, claims=kept)


_BY_STATUS: dict[DraftStatus, Callable[[DraftAnswer, list[Claim]], CopilotResponse]] = {
    "insufficient_evidence": _no_evidence,
    "answer": _as_answer,
    "ambiguous": _as_ambiguous,
    "missing_inputs": _as_missing_inputs,
}


def validate_draft(draft: DraftAnswer, passages: list[Chunk]) -> CopilotResponse:
    kept = _kept_claims(draft, passages)
    return _BY_STATUS[draft.status](draft, kept)

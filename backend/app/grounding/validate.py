
from __future__ import annotations

import re
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
    DraftClaim,
    DraftStatus,
    Refusal,
)
from app.retrieval.refs import section_path, select_section_ids

_HYPHEN_BREAK = re.compile(r"(?<=\w)-\s+(?=\w)")
_WORD_HYPHEN = re.compile(r"(?<=\w)-(?=\w)")


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def normalize_quote(text: str) -> str:
    """Fold joined hyphens and table newlines so a verbatim quote still matches."""
    joined = _HYPHEN_BREAK.sub("-", text)
    return normalize_space(_WORD_HYPHEN.sub(" ", joined))


def _resolve_passage_ids(raw_ids: list[str], passages: list[Chunk]) -> list[str] | None:
    allowed = {passage.id for passage in passages}
    rows = [(passage.id, passage.section) for passage in passages]
    resolved: list[str] = []
    seen: set[str] = set()
    for raw in raw_ids:
        matched: list[str]
        if raw in allowed:
            matched = [raw]
        else:
            matched = select_section_ids(rows, raw)
            if not matched:
                path = section_path(raw)
                if path and path != raw:
                    matched = select_section_ids(rows, path)
        if not matched:
            return None
        for passage_id in matched:
            if passage_id in seen:
                continue
            seen.add(passage_id)
            resolved.append(passage_id)
    return resolved


def _quote_in_cited_passages(claim: DraftClaim, by_id: dict[str, Chunk]) -> bool:
    quote = normalize_quote(claim.quote)
    if not quote:
        return False
    bodies = [normalize_quote(by_id[passage_id].text) for passage_id in claim.passage_ids]
    if any(quote in body for body in bodies):
        return True
    return quote in " ".join(bodies)


def _to_claim(claim: DraftClaim) -> Claim:
    return Claim(text=claim.text, passage_ids=claim.passage_ids, quote=claim.quote)


def _kept_claims(draft: DraftAnswer, passages: list[Chunk]) -> list[Claim]:
    by_id = {passage.id: passage for passage in passages}
    kept: list[Claim] = []
    for claim in draft.claims:
        if not claim.passage_ids:
            continue
        resolved = _resolve_passage_ids(claim.passage_ids, passages)
        if resolved is None:
            continue
        mapped = claim.model_copy(update={"passage_ids": resolved})
        if not _quote_in_cited_passages(mapped, by_id):
            continue
        kept.append(_to_claim(mapped))
    return kept


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

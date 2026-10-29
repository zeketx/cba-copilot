
from __future__ import annotations

from app.domain import (
    CITATIONS_DROPPED_MESSAGE,
    NO_EVIDENCE_MESSAGE,
    Chunk,
    CitedAnswer,
    DraftAnswer,
    Refusal,
)


def validate_draft(draft: DraftAnswer, passages: list[Chunk]) -> CitedAnswer | Refusal:
    if draft.insufficient_evidence or not draft.claims:
        return Refusal(reason="no_evidence", message=NO_EVIDENCE_MESSAGE)

    allowed = {passage.id for passage in passages}
    kept = [
        claim
        for claim in draft.claims
        if claim.passage_ids and all(passage_id in allowed for passage_id in claim.passage_ids)
    ]
    if not kept:
        return Refusal(reason="citations_dropped", message=CITATIONS_DROPPED_MESSAGE)
    return CitedAnswer(claims=kept)

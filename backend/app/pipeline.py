
from __future__ import annotations

from app.assistant.drafter import Drafter
from app.domain import NO_EVIDENCE_MESSAGE, CopilotResponse, Refusal
from app.grounding.validate import validate_draft
from app.retrieval.embed import Embedder
from app.retrieval.hybrid import evidence_is_adequate, hybrid_retrieve
from app.retrieval.store import ChunkStore


def answer_question(
    question: str,
    store: ChunkStore,
    embedder: Embedder,
    drafter: Drafter,
    *,
    candidate_k: int = 50,
    top_k: int = 8,
    rrf_k: int = 60,
    context_per_hit: int = 4,
    context_max: int = 16,
) -> CopilotResponse:
    retrieved = hybrid_retrieve(
        store,
        question,
        embedder,
        candidate_k=candidate_k,
        top_k=top_k,
        rrf_k=rrf_k,
        context_per_hit=context_per_hit,
        context_max=context_max,
    )
    if not evidence_is_adequate(question, retrieved.hits):
        return Refusal(reason="no_evidence", message=NO_EVIDENCE_MESSAGE)
    passages = retrieved.passages()
    draft = drafter.draft(question, passages)
    return validate_draft(draft, passages)

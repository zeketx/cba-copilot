
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.assistant.drafter import OverlapDrafter
from app.config import Settings
from app.definitions import load_definitions
from app.demo import demo_embedder, demo_store, load_demo_chunks
from app.domain import Chunk, CitedAnswer, Refusal
from app.pipeline import answer_question


class AskRequest(BaseModel):
    question: str = Field(min_length=1)

class PublicCitation(BaseModel):
    passage_id: str
    article_number: int | None
    article_title: str
    section: str
    page_start: int | None
    page_end: int | None
    source_url: str
    excerpt: str

class PublicClaim(BaseModel):
    text: str
    citations: list[PublicCitation]

class PublicAnswer(BaseModel):
    kind: Literal["answer"] = "answer"
    claims: list[PublicClaim]

class PublicRefusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: Literal["no_evidence", "citations_dropped"]
    message: str

PublicResponse = Annotated[PublicAnswer | PublicRefusal, Field(discriminator="kind")]

def _excerpt(text: str, limit: int = 420) -> str:
    trimmed = " ".join(text.split())
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[: limit - 3] + "..."

def _citation(chunk: Chunk) -> PublicCitation:
    return PublicCitation(
        passage_id=chunk.id,
        article_number=chunk.article_number,
        article_title=chunk.article_title,
        section=chunk.section,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        source_url=chunk.source_url,
        excerpt=_excerpt(chunk.text),
    )

def to_public(
    response: CitedAnswer | Refusal,
    passages: dict[str, Chunk],
) -> PublicAnswer | PublicRefusal:
    if isinstance(response, Refusal):
        return PublicRefusal(reason=response.reason, message=response.message)
    claims: list[PublicClaim] = []
    for claim in response.claims:
        citations = [
            _citation(passages[passage_id])
            for passage_id in claim.passage_ids
            if passage_id in passages
        ]
        claims.append(PublicClaim(text=claim.text, citations=citations))
    return PublicAnswer(claims=claims)

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = demo_store()
    embedder = demo_embedder(settings.openai_embedding_dimensions)
    drafter = OverlapDrafter()
    by_id = {chunk.id: chunk for chunk in load_demo_chunks()}
    app = FastAPI(title="CBA Copilot", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "mode": "fake"}

    @app.post("/api/ask")
    def ask(body: AskRequest) -> PublicAnswer | PublicRefusal:
        result = answer_question(
            body.question,
            store,
            embedder,
            drafter,
            candidate_k=settings.retrieval_candidate_k,
            top_k=settings.retrieval_top_k,
            rrf_k=settings.retrieval_rrf_k,
        )
        return to_public(result, by_id)

    @app.get("/api/definitions")
    def definitions() -> dict[str, object]:
        return load_definitions()

    return app

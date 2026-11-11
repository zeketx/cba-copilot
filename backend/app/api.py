
from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.assistant.drafter import OverlapDrafter
from app.auth.dependencies import gate_from_settings, get_current_user, http_error
from app.auth.identity import AppUser, AuthError, Email
from app.chat.log import ChatLog, MemoryChatLog, SqlChatLog
from app.chat.model import StoredTurn, ThreadSummary
from app.chat.service import ThreadChat
from app.config import Settings
from app.definitions import load_definitions
from app.demo import demo_embedder, demo_store, load_demo_chunks
from app.domain import Chunk, CitedAnswer, Refusal
from app.pipeline import answer_question
from app.source_view import ElementPlacement, SpanPlacement, render_source

if TYPE_CHECKING:
    from app.auth.gate import AccessGate


class AskRequest(BaseModel):
    question: str = Field(min_length=1)

class AccessRequestBody(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalized(cls, value: str) -> str:
        return Email.parse(value).value

class AccessRequestResponse(BaseModel):
    email: str
    created_at: datetime

class PublicCitation(BaseModel):
    passage_id: str
    article_number: int | None
    article_title: str
    section: str
    page_or_section: str
    page_start: int | None
    page_end: int | None
    source_url: str
    excerpt: str
    source_html: str
    placement: SpanPlacement | ElementPlacement

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


class PublicThread(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class PublicUserMessage(BaseModel):
    id: UUID
    role: Literal["user"] = "user"
    position: int
    text: str


class PublicAssistantMessage(BaseModel):
    id: UUID
    role: Literal["assistant"] = "assistant"
    position: int
    response: PublicAnswer | PublicRefusal


class StreamChatMessage(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class StreamAskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: UUID = Field(alias="threadId")
    messages: list[StreamChatMessage] = Field(min_length=1)

    @model_validator(mode="after")
    def last_message_is_user(self) -> StreamAskRequest:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be a user turn")
        return self

def _excerpt(text: str, limit: int = 420) -> str:
    trimmed = " ".join(text.split())
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[: limit - 3] + "..."

def _page_or_section(chunk: Chunk) -> str:
    if chunk.page_start is None:
        return chunk.section
    if chunk.page_end is None or chunk.page_end == chunk.page_start:
        return f"{chunk.section}, p. {chunk.page_start}"
    return f"{chunk.section}, pp. {chunk.page_start}-{chunk.page_end}"


def _citation(chunk: Chunk, corpus: list[Chunk]) -> PublicCitation:
    source_html, placement = render_source(chunk, corpus)
    return PublicCitation(
        passage_id=chunk.id,
        article_number=chunk.article_number,
        article_title=chunk.article_title,
        section=chunk.section,
        page_or_section=_page_or_section(chunk),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        source_url=chunk.source_url,
        excerpt=_excerpt(chunk.text),
        source_html=source_html,
        placement=placement,
    )

def to_public(
    response: CitedAnswer | Refusal,
    passages: dict[str, Chunk],
    corpus: list[Chunk],
) -> PublicAnswer | PublicRefusal:
    if isinstance(response, Refusal):
        return PublicRefusal(reason=response.reason, message=response.message)
    claims: list[PublicClaim] = []
    for claim in response.claims:
        citations = [
            _citation(passages[passage_id], corpus)
            for passage_id in claim.passage_ids
            if passage_id in passages
        ]
        claims.append(PublicClaim(text=claim.text, citations=citations))
    return PublicAnswer(claims=claims)

def _public_thread(summary: ThreadSummary) -> PublicThread:
    return PublicThread(
        id=summary.id,
        title=summary.title,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def _stream_text(public: PublicAnswer | PublicRefusal) -> str:
    if isinstance(public, PublicRefusal):
        return public.message
    return "\n\n".join(claim.text for claim in public.claims)


def _delta_chunks(text: str, size: int = 48) -> list[str]:
    if not text:
        return [""]
    return [text[index : index + size] for index in range(0, len(text), size)]


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _turn_events(
    turn: StoredTurn,
    public: PublicAnswer | PublicRefusal,
) -> Iterator[str]:
    for chunk in _delta_chunks(_stream_text(public)):
        yield _sse("delta", {"text": chunk})
    if isinstance(public, PublicAnswer):
        claims = [claim.model_dump(mode="json") for claim in public.claims]
        yield _sse("citations", {"claims": claims})
    yield _sse(
        "done",
        {
            "thread_id": str(turn.thread_id),
            "turn_id": str(turn.turn_id),
            "response": public.model_dump(mode="json"),
        },
    )


def _chat_log(settings: Settings) -> ChatLog:
    if settings.database_url:
        return SqlChatLog(settings.sqlalchemy_database_url)
    return MemoryChatLog()


def create_app(
    settings: Settings | None = None,
    *,
    gate: AccessGate | None = None,
    log: ChatLog | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = demo_store()
    embedder = demo_embedder()
    drafter = OverlapDrafter()
    by_id = {chunk.id: chunk for chunk in load_demo_chunks()}
    corpus = list(by_id.values())
    chat_log = log if log is not None else _chat_log(settings)
    app = FastAPI(title="CBA Copilot", version="0.1.0")
    app.state.gate = gate if gate is not None else gate_from_settings(settings, threads=chat_log)
    app.state.chat_log = chat_log
    app.state.chat = ThreadChat(
        app.state.gate,
        chat_log,
        lambda question: answer_question(
            question,
            store,
            embedder,
            drafter,
            candidate_k=settings.retrieval_candidate_k,
            top_k=settings.retrieval_top_k,
            rrf_k=settings.retrieval_rrf_k,
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "mode": "fake"}

    @app.post("/api/access-requests")
    def request_access(body: AccessRequestBody, request: Request) -> AccessRequestResponse:
        record = request.app.state.gate.submit(Email.parse(body.email))
        return AccessRequestResponse(email=record.email.value, created_at=record.created_at)

    @app.post("/api/threads")
    def create_thread(
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> PublicThread:
        return _public_thread(request.app.state.chat_log.create_thread(user.id))

    @app.get("/api/threads")
    def list_threads(
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> list[PublicThread]:
        return [_public_thread(item) for item in request.app.state.chat_log.list_threads(user.id)]

    @app.get("/api/threads/{thread_id}")
    def open_thread(
        thread_id: UUID,
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> dict[str, str]:
        try:
            request.app.state.gate.open_thread(user, thread_id)
        except AuthError as exc:
            raise http_error(exc) from None
        return {"id": str(thread_id)}

    @app.get("/api/threads/{thread_id}/messages")
    def thread_messages(
        thread_id: UUID,
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> list[PublicUserMessage | PublicAssistantMessage]:
        try:
            request.app.state.gate.open_thread(user, thread_id)
        except AuthError as exc:
            raise http_error(exc) from None
        messages: list[PublicUserMessage | PublicAssistantMessage] = []
        for turn in request.app.state.chat_log.list_turns(thread_id):
            messages.append(
                PublicUserMessage(id=turn.turn_id, position=turn.user_position, text=turn.question)
            )
            messages.append(
                PublicAssistantMessage(
                    id=turn.assistant_id,
                    position=turn.assistant_position,
                    response=to_public(turn.outcome, by_id, corpus),
                )
            )
        return messages

    @app.post("/api/chat/stream")
    def chat_stream(
        body: StreamAskRequest,
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> StreamingResponse:
        last = body.messages[-1]
        try:
            turn = request.app.state.chat.ask(user, body.thread_id, last.id, last.content)
        except AuthError as exc:
            raise http_error(exc) from None
        public = to_public(turn.outcome, by_id, corpus)
        return StreamingResponse(_turn_events(turn, public), media_type="text/event-stream")

    @app.post("/api/ask", dependencies=[Depends(get_current_user)])
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
        return to_public(result, by_id, list(by_id.values()))

    @app.get("/api/definitions")
    def definitions() -> dict[str, object]:
        return load_definitions()

    return app

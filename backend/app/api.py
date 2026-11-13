
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.assistant.drafter import OverlapDrafter, build_live_drafter
from app.auth.dependencies import gate_from_settings, get_current_user, http_error
from app.auth.identity import AppUser, AuthError, Email
from app.chat.log import ChatLog, MemoryChatLog, SqlChatLog
from app.chat.model import StoredTurn, ThreadSummary
from app.chat.service import AnswerFailed, AnswerFn, ThreadChat
from app.config import AppMode, Settings, require_app_mode
from app.definitions import load_definitions
from app.demo import demo_embedder, demo_store, load_demo_chunks
from app.domain import Chunk, Claim, Clarification, CopilotResponse, Refusal
from app.limits import DistinctCap, SlidingWindow
from app.pipeline import answer_question
from app.retrieval.embed import build_embedder
from app.retrieval.store import ChunkStore, PostgresChunkStore, postgres_session_factory
from app.source_view import ElementPlacement, SpanPlacement, render_source

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.auth.gate import AccessGate


# Character length, same as len(). Oversized bodies are 422 before an answer runs.
MAX_MESSAGE_CHARS = 4_000
MAX_CHAT_MESSAGES = 32


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

class AccessRequestBody(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalized(cls, value: str) -> str:
        return Email.parse(value).value

class AccessRequestResponse(BaseModel):
    email: str
    created_at: datetime


class MeResponse(BaseModel):
    email: str

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


class PublicClarification(BaseModel):
    kind: Literal["clarification"] = "clarification"
    reason: Literal["ambiguous", "missing_inputs"]
    message: str
    claims: list[PublicClaim]

PublicResponse = Annotated[
    PublicAnswer | PublicRefusal | PublicClarification,
    Field(discriminator="kind"),
]


class PublicThread(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class RenameThreadBody(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def stripped_title(cls, value: str) -> str:
        title = value.strip()
        if not title or len(title) > 80:
            raise ValueError("title must be 1 to 80 characters")
        return title


class PublicUserMessage(BaseModel):
    id: UUID
    role: Literal["user"] = "user"
    position: int
    text: str


class PublicAssistantMessage(BaseModel):
    id: UUID
    role: Literal["assistant"] = "assistant"
    position: int
    response: PublicAnswer | PublicRefusal | PublicClarification


class StreamChatMessage(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class StreamAskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: UUID = Field(alias="threadId")
    messages: list[StreamChatMessage] = Field(min_length=1, max_length=MAX_CHAT_MESSAGES)

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

def _public_claims(
    claims: list[Claim],
    passages: dict[str, Chunk],
    corpus: list[Chunk],
) -> list[PublicClaim]:
    public: list[PublicClaim] = []
    for claim in claims:
        citations = [
            _citation(passages[passage_id], corpus)
            for passage_id in claim.passage_ids
            if passage_id in passages
        ]
        public.append(PublicClaim(text=claim.text, citations=citations))
    return public


def to_public(
    response: CopilotResponse,
    passages: dict[str, Chunk],
    corpus: list[Chunk],
) -> PublicAnswer | PublicRefusal | PublicClarification:
    if isinstance(response, Refusal):
        return PublicRefusal(reason=response.reason, message=response.message)
    claims = _public_claims(response.claims, passages, corpus)
    if isinstance(response, Clarification):
        return PublicClarification(reason=response.reason, message=response.message, claims=claims)
    return PublicAnswer(claims=claims)


_turn_chunks: ContextVar[dict[str, Chunk]] = ContextVar("turn_chunks")


def _claim_passage_ids(response: CopilotResponse) -> list[str]:
    if isinstance(response, Refusal):
        return []
    ids: list[str] = []
    for claim in response.claims:
        ids.extend(claim.passage_ids)
    return ids


def _resolve_passages(
    response: CopilotResponse,
    known: dict[str, Chunk],
    store: ChunkStore | None,
) -> dict[str, Chunk]:
    passages: dict[str, Chunk] = {}
    for passage_id in _claim_passage_ids(response):
        chunk = known.get(passage_id)
        if chunk is None and store is not None:
            chunk = store.get(passage_id)
        if chunk is not None:
            passages[passage_id] = chunk
    return passages


def _publish(
    response: CopilotResponse,
    known: dict[str, Chunk],
    store: ChunkStore | None,
) -> PublicAnswer | PublicRefusal | PublicClarification:
    passages = _resolve_passages(response, known, store)
    corpus = list(known.values()) if known else list(passages.values())
    return to_public(response, passages, corpus)

def _public_thread(summary: ThreadSummary) -> PublicThread:
    return PublicThread(
        id=summary.id,
        title=summary.title,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def _stream_text(public: PublicAnswer | PublicRefusal | PublicClarification) -> str:
    if isinstance(public, PublicRefusal | PublicClarification):
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
    public: PublicAnswer | PublicRefusal | PublicClarification,
) -> Iterator[str]:
    for chunk in _delta_chunks(_stream_text(public)):
        yield _sse("delta", {"text": chunk})
    if not isinstance(public, PublicRefusal):
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


def _client_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _too_many(error: str) -> HTTPException:
    return HTTPException(status_code=429, detail={"error": error})


def _chat_log(settings: Settings) -> ChatLog:
    if settings.database_url:
        return SqlChatLog(settings.sqlalchemy_database_url)
    return MemoryChatLog()


def create_app(
    settings: Settings | None = None,
    *,
    gate: AccessGate | None = None,
    log: ChatLog | None = None,
    answer: AnswerFn | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    mode = require_app_mode(settings)
    demo_chunks = {chunk.id: chunk for chunk in load_demo_chunks()}
    memory_store = demo_store()
    offline_embedder = demo_embedder()
    offline_drafter = OverlapDrafter()
    open_session = session_factory
    if mode is AppMode.live and open_session is None:
        open_session = postgres_session_factory(settings.sqlalchemy_database_url)
    live_embedder = None
    live_drafter = None
    if mode is AppMode.live and answer is None:
        live_embedder = build_embedder(settings)
        live_drafter = build_live_drafter(settings)
    chat_log = log if log is not None else _chat_log(settings)
    answer_kwargs = {
        "candidate_k": settings.retrieval_candidate_k,
        "top_k": settings.retrieval_top_k,
        "rrf_k": settings.retrieval_rrf_k,
        "context_per_hit": settings.retrieval_context_per_hit,
        "context_max": settings.retrieval_context_max,
    }

    def run_answer(question: str) -> CopilotResponse:
        if mode is AppMode.demo:
            if answer is not None:
                result = answer(question)
            else:
                result = answer_question(
                    question,
                    memory_store,
                    offline_embedder,
                    offline_drafter,
                    **answer_kwargs,
                )
            _turn_chunks.set(_resolve_passages(result, demo_chunks, memory_store))
            return result
        assert open_session is not None
        session = open_session()
        try:
            if answer is not None:
                result = answer(question)
                _turn_chunks.set({})
                return result
            store = PostgresChunkStore(session)
            assert live_embedder is not None
            assert live_drafter is not None
            result = answer_question(
                question,
                store,
                live_embedder,
                live_drafter,
                **answer_kwargs,
            )
            _turn_chunks.set(_resolve_passages(result, {}, store))
            return result
        finally:
            session.close()

    def public_outcome(
        response: CopilotResponse,
        *,
        reload: bool = False,
    ) -> PublicAnswer | PublicRefusal | PublicClarification:
        if mode is AppMode.demo:
            return _publish(response, demo_chunks, memory_store)
        if not reload:
            try:
                cached = _turn_chunks.get()
            except LookupError:
                cached = None
            if cached is not None:
                return _publish(response, cached, None)
        assert open_session is not None
        session = open_session()
        try:
            return _publish(response, {}, PostgresChunkStore(session))
        finally:
            session.close()

    answer_window = SlidingWindow(
        limit=settings.answer_rate_limit,
        window_seconds=settings.answer_rate_window_seconds,
    )
    access_window = SlidingWindow(
        limit=settings.access_request_rate_limit,
        window_seconds=settings.access_request_rate_window_seconds,
    )
    access_cap = DistinctCap(settings.access_request_cap)
    app = FastAPI(title="CBA Copilot", version="0.1.0")
    app.state.gate = gate if gate is not None else gate_from_settings(settings, threads=chat_log)
    app.state.chat_log = chat_log
    app.state.chat = ThreadChat(app.state.gate, chat_log, run_answer)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "mode": mode.health_label}

    @app.post("/api/access-requests")
    def request_access(body: AccessRequestBody, request: Request) -> AccessRequestResponse:
        if not access_window.allow(_client_host(request)):
            raise _too_many("rate_limited")
        if not access_cap.reserve(body.email):
            raise _too_many("access_requests_full")
        record = request.app.state.gate.submit(Email.parse(body.email))
        return AccessRequestResponse(email=record.email.value, created_at=record.created_at)

    @app.get("/api/me")
    def me(user: Annotated[AppUser, Depends(get_current_user)]) -> MeResponse:
        return MeResponse(email=user.email.value)

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

    @app.patch("/api/threads/{thread_id}")
    def rename_thread(
        thread_id: UUID,
        body: RenameThreadBody,
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> PublicThread:
        try:
            request.app.state.gate.open_thread(user, thread_id)
        except AuthError as exc:
            raise http_error(exc) from None
        return _public_thread(request.app.state.chat_log.rename_thread(thread_id, body.title))

    @app.delete("/api/threads/{thread_id}", status_code=204)
    def delete_thread(
        thread_id: UUID,
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> None:
        try:
            request.app.state.gate.open_thread(user, thread_id)
        except AuthError as exc:
            raise http_error(exc) from None
        request.app.state.chat_log.delete_thread(thread_id)

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
                    response=public_outcome(turn.outcome, reload=True),
                )
            )
        return messages

    @app.post("/api/chat/stream")
    def chat_stream(
        body: StreamAskRequest,
        request: Request,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> StreamingResponse:
        if not answer_window.allow(str(user.id.value)):
            raise _too_many("rate_limited")
        last = body.messages[-1]
        try:
            turn = request.app.state.chat.ask(user, body.thread_id, last.id, last.content)
        except AuthError as exc:
            raise http_error(exc) from None
        except AnswerFailed:
            logger.exception("answer failed")
            raise HTTPException(status_code=502, detail={"error": "answer_failed"}) from None
        public = public_outcome(turn.outcome)
        return StreamingResponse(_turn_events(turn, public), media_type="text/event-stream")

    @app.post("/api/ask")
    def ask(
        body: AskRequest,
        user: Annotated[AppUser, Depends(get_current_user)],
    ) -> PublicAnswer | PublicRefusal | PublicClarification:
        if not answer_window.allow(str(user.id.value)):
            raise _too_many("rate_limited")
        try:
            result = run_answer(body.question)
        except Exception:
            logger.exception("answer failed")
            raise HTTPException(status_code=502, detail={"error": "answer_failed"}) from None
        return public_outcome(result)

    @app.get("/api/definitions")
    def definitions() -> dict[str, object]:
        return load_definitions()

    return app

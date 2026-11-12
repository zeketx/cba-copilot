from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import create_engine, delete, func, insert, select, update
from sqlalchemy.engine import Engine

from app.auth.identity import AuthUserId
from app.chat.model import StoredTurn, ThreadSummary, uuid_chunk_ids
from app.domain import CopilotResponse, Refusal

_OUTCOME = TypeAdapter(CopilotResponse)


class ChatLog(Protocol):
    def owner_id(self, thread_id: UUID) -> AuthUserId | None: ...

    def create_thread(self, owner: AuthUserId) -> ThreadSummary: ...

    def list_threads(self, owner: AuthUserId) -> list[ThreadSummary]: ...

    def rename_thread(self, thread_id: UUID, title: str) -> ThreadSummary: ...

    def delete_thread(self, thread_id: UUID) -> None: ...

    def list_turns(self, thread_id: UUID) -> list[StoredTurn]: ...

    def get_turn(self, thread_id: UUID, turn_id: UUID) -> StoredTurn | None: ...

    def commit_turn(
        self,
        owner: AuthUserId,
        thread_id: UUID,
        turn_id: UUID,
        question: str,
        outcome: CopilotResponse,
    ) -> StoredTurn: ...


class MemoryChatLog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._owners: dict[UUID, AuthUserId] = {}
        self._threads: dict[UUID, ThreadSummary] = {}
        self._turns: dict[UUID, list[StoredTurn]] = {}
        self._by_turn_id: dict[UUID, StoredTurn] = {}

    def owner_id(self, thread_id: UUID) -> AuthUserId | None:
        with self._lock:
            return self._owners.get(thread_id)

    def create_thread(self, owner: AuthUserId) -> ThreadSummary:
        now = datetime.now(timezone.utc)
        summary = ThreadSummary(id=uuid4(), title="", created_at=now, updated_at=now)
        with self._lock:
            self._owners[summary.id] = owner
            self._threads[summary.id] = summary
            self._turns[summary.id] = []
        return summary

    def list_threads(self, owner: AuthUserId) -> list[ThreadSummary]:
        with self._lock:
            owned = [
                summary
                for thread_id, summary in self._threads.items()
                if self._owners[thread_id] == owner
            ]
        return sorted(owned, key=lambda item: item.updated_at, reverse=True)

    def rename_thread(self, thread_id: UUID, title: str) -> ThreadSummary:
        with self._lock:
            summary = self._threads[thread_id]
            updated = ThreadSummary(
                id=summary.id,
                title=title,
                created_at=summary.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._threads[thread_id] = updated
            return updated

    def delete_thread(self, thread_id: UUID) -> None:
        with self._lock:
            turns = self._turns.pop(thread_id, [])
            for turn in turns:
                self._by_turn_id.pop(turn.turn_id, None)
            self._owners.pop(thread_id, None)
            self._threads.pop(thread_id, None)

    def list_turns(self, thread_id: UUID) -> list[StoredTurn]:
        with self._lock:
            return list(self._turns.get(thread_id, ()))

    def get_turn(self, thread_id: UUID, turn_id: UUID) -> StoredTurn | None:
        with self._lock:
            stored = self._by_turn_id.get(turn_id)
            if stored is None or stored.thread_id != thread_id:
                return None
            return stored

    def commit_turn(
        self,
        owner: AuthUserId,
        thread_id: UUID,
        turn_id: UUID,
        question: str,
        outcome: CopilotResponse,
    ) -> StoredTurn:
        with self._lock:
            existing = self._by_turn_id.get(turn_id)
            if existing is not None:
                if existing.thread_id != thread_id:
                    raise KeyError(turn_id)
                return existing
            if self._owners.get(thread_id) != owner:
                raise KeyError(thread_id)
            prior = self._turns[thread_id]
            user_position = 2 * len(prior)
            turn = StoredTurn(
                thread_id=thread_id,
                turn_id=turn_id,
                question=question,
                user_position=user_position,
                assistant_id=uuid4(),
                assistant_position=user_position + 1,
                outcome=outcome,
            )
            prior.append(turn)
            self._by_turn_id[turn_id] = turn
            summary = self._threads[thread_id]
            title = summary.title or question.strip()[:80]
            self._threads[thread_id] = ThreadSummary(
                id=summary.id,
                title=title,
                created_at=summary.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            return turn


class SqlChatLog:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Engine | None = None

    def _connect(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._database_url)
        return self._engine

    def owner_id(self, thread_id: UUID) -> AuthUserId | None:
        from app.database.models import ChatThread

        with self._connect().connect() as connection:
            row = connection.execute(
                select(ChatThread.user_id).where(ChatThread.id == thread_id)
            ).one_or_none()
        if row is None:
            return None
        return AuthUserId(value=row.user_id)

    def create_thread(self, owner: AuthUserId) -> ThreadSummary:
        from app.database.models import ChatThread

        with self._connect().begin() as connection:
            row = connection.execute(
                insert(ChatThread)
                .values(user_id=owner.value, title="")
                .returning(
                    ChatThread.id,
                    ChatThread.title,
                    ChatThread.created_at,
                    ChatThread.updated_at,
                )
            ).one()
        return ThreadSummary(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_threads(self, owner: AuthUserId) -> list[ThreadSummary]:
        from app.database.models import ChatThread

        with self._connect().connect() as connection:
            rows = connection.execute(
                select(
                    ChatThread.id,
                    ChatThread.title,
                    ChatThread.created_at,
                    ChatThread.updated_at,
                )
                .where(ChatThread.user_id == owner.value)
                .order_by(ChatThread.updated_at.desc())
            ).all()
        return [
            ThreadSummary(
                id=row.id,
                title=row.title,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def rename_thread(self, thread_id: UUID, title: str) -> ThreadSummary:
        from app.database.models import ChatThread

        with self._connect().begin() as connection:
            row = connection.execute(
                update(ChatThread)
                .where(ChatThread.id == thread_id)
                .values(title=title, updated_at=func.now())
                .returning(
                    ChatThread.id,
                    ChatThread.title,
                    ChatThread.created_at,
                    ChatThread.updated_at,
                )
            ).one_or_none()
        if row is None:
            raise KeyError(thread_id)
        return ThreadSummary(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def delete_thread(self, thread_id: UUID) -> None:
        from app.database.models import ChatThread

        with self._connect().begin() as connection:
            connection.execute(delete(ChatThread).where(ChatThread.id == thread_id))

    def list_turns(self, thread_id: UUID) -> list[StoredTurn]:
        from app.database.models import ChatMessage

        with self._connect().connect() as connection:
            rows = connection.execute(
                select(
                    ChatMessage.id,
                    ChatMessage.role,
                    ChatMessage.position,
                    ChatMessage.message,
                )
                .where(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.position)
            ).all()
        return _turns_from_rows(thread_id, rows)

    def get_turn(self, thread_id: UUID, turn_id: UUID) -> StoredTurn | None:
        from app.database.models import ChatMessage

        with self._connect().connect() as connection:
            user = connection.execute(
                select(
                    ChatMessage.id,
                    ChatMessage.role,
                    ChatMessage.position,
                    ChatMessage.message,
                ).where(ChatMessage.id == turn_id, ChatMessage.thread_id == thread_id)
            ).one_or_none()
            if user is None or user.role != "user":
                return None
            assistant = connection.execute(
                select(
                    ChatMessage.id,
                    ChatMessage.role,
                    ChatMessage.position,
                    ChatMessage.message,
                ).where(
                    ChatMessage.thread_id == thread_id,
                    ChatMessage.position == user.position + 1,
                )
            ).one_or_none()
        if assistant is None or assistant.role != "assistant":
            return None
        return _turn_from_pair(thread_id, user, assistant)

    def commit_turn(
        self,
        owner: AuthUserId,
        thread_id: UUID,
        turn_id: UUID,
        question: str,
        outcome: CopilotResponse,
    ) -> StoredTurn:
        existing = self.get_turn(thread_id, turn_id)
        if existing is not None:
            return existing
        from app.database.models import ChatMessage, ChatThread, MessageCitation

        assistant_id = uuid4()
        payload = outcome.model_dump(mode="json")
        chunk_ids = uuid_chunk_ids(_passage_ids(outcome))
        with self._connect().begin() as connection:
            thread = connection.execute(
                select(ChatThread.id, ChatThread.user_id, ChatThread.title)
                .where(ChatThread.id == thread_id)
                .with_for_update()
            ).one_or_none()
            if thread is None or thread.user_id != owner.value:
                raise KeyError(thread_id)
            stored = connection.execute(
                select(
                    ChatMessage.id,
                    ChatMessage.role,
                    ChatMessage.position,
                    ChatMessage.message,
                ).where(ChatMessage.id == turn_id, ChatMessage.thread_id == thread_id)
            ).one_or_none()
            if stored is not None:
                assistant = connection.execute(
                    select(
                        ChatMessage.id,
                        ChatMessage.role,
                        ChatMessage.position,
                        ChatMessage.message,
                    ).where(
                        ChatMessage.thread_id == thread_id,
                        ChatMessage.position == stored.position + 1,
                    )
                ).one()
                return _turn_from_pair(thread_id, stored, assistant)
            count = connection.execute(
                select(func.count())
                .select_from(ChatMessage)
                .where(ChatMessage.thread_id == thread_id)
            ).scalar_one()
            user_position = count
            connection.execute(
                insert(ChatMessage).values(
                    id=turn_id,
                    thread_id=thread_id,
                    role="user",
                    position=user_position,
                    message={"text": question},
                )
            )
            connection.execute(
                insert(ChatMessage).values(
                    id=assistant_id,
                    thread_id=thread_id,
                    role="assistant",
                    position=user_position + 1,
                    message=payload,
                )
            )
            if chunk_ids:
                connection.execute(
                    insert(MessageCitation),
                    [
                        {
                            "message_id": assistant_id,
                            "chunk_id": chunk_id,
                            "sort_index": index,
                        }
                        for index, chunk_id in enumerate(chunk_ids)
                    ],
                )
            title = thread.title or question.strip()[:80]
            connection.execute(
                update(ChatThread)
                .where(ChatThread.id == thread_id)
                .values(title=title, updated_at=func.now())
            )
        return StoredTurn(
            thread_id=thread_id,
            turn_id=turn_id,
            question=question,
            user_position=user_position,
            assistant_id=assistant_id,
            assistant_position=user_position + 1,
            outcome=outcome,
        )


def _passage_ids(outcome: CopilotResponse) -> list[str]:
    if isinstance(outcome, Refusal):
        return []
    ids: list[str] = []
    for claim in outcome.claims:
        ids.extend(claim.passage_ids)
    return ids


def _turns_from_rows(thread_id: UUID, rows: list[object]) -> list[StoredTurn]:
    turns: list[StoredTurn] = []
    index = 0
    while index + 1 < len(rows):
        user = rows[index]
        assistant = rows[index + 1]
        if user.role != "user" or assistant.role != "assistant":
            raise ValueError("chat log has a broken turn")
        turns.append(_turn_from_pair(thread_id, user, assistant))
        index += 2
    if index < len(rows):
        raise ValueError("chat log has a broken turn")
    return turns


def _turn_from_pair(thread_id: UUID, user: object, assistant: object) -> StoredTurn:
    return StoredTurn(
        thread_id=thread_id,
        turn_id=user.id,
        question=user.message["text"],
        user_position=user.position,
        assistant_id=assistant.id,
        assistant_position=assistant.position,
        outcome=_OUTCOME.validate_python(assistant.message),
    )

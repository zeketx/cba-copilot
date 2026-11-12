from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.auth.gate import AccessGate
from app.auth.identity import AppUser
from app.chat.log import ChatLog
from app.chat.model import StoredTurn
from app.domain import CopilotResponse

AnswerFn = Callable[[str], CopilotResponse]


class AnswerFailed(Exception):
    pass


class ThreadChat:
    def __init__(self, gate: AccessGate, log: ChatLog, answer: AnswerFn) -> None:
        self._gate = gate
        self._log = log
        self._answer = answer

    def ask(self, viewer: AppUser, thread_id: UUID, turn_id: UUID, question: str) -> StoredTurn:
        self._gate.open_thread(viewer, thread_id)
        existing = self._log.get_turn(thread_id, turn_id)
        if existing is not None:
            return existing
        try:
            outcome = self._answer(question)
        except Exception as exc:
            raise AnswerFailed from exc
        return self._log.commit_turn(viewer.id, thread_id, turn_id, question, outcome)

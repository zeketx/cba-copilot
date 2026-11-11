from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain import CopilotResponse


def uuid_chunk_ids(passage_ids: list[str]) -> list[UUID]:
    if not passage_ids:
        return []
    parsed: list[UUID] = []
    for passage_id in passage_ids:
        try:
            parsed.append(UUID(passage_id))
        except ValueError:
            return []
    return parsed


@dataclass(frozen=True, slots=True)
class ThreadSummary:
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredTurn:
    thread_id: UUID
    turn_id: UUID
    question: str
    user_position: int
    assistant_id: UUID
    assistant_position: int
    outcome: CopilotResponse

    def __post_init__(self) -> None:
        if self.user_position < 0 or self.user_position % 2 != 0:
            raise ValueError("user_position must be an even index")
        if self.assistant_position != self.user_position + 1:
            raise ValueError("assistant_position must be user_position + 1")

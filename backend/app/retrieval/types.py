from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.domain import Chunk


class DocumentMeta(BaseModel):
    id: str
    title: str
    source_url: str
    sha256: str | None = None
    cover_date: str | None = None
    printed_term: str | None = None
    page_offset: int | None = None
    effective_start: str = ""
    effective_through: str = ""


@dataclass
class LoadedContext:
    neighbors: dict[str, tuple[Chunk | None, Chunk | None]] = field(default_factory=dict)
    articles: dict[int, list[Chunk]] = field(default_factory=dict)
    documents: list[DocumentMeta] = field(default_factory=list)


class Retrieval(BaseModel):
    hits: list[Chunk]
    context: list[Chunk] = Field(default_factory=list)
    documents: list[DocumentMeta] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)

    def passages(self) -> list[Chunk]:
        return [*self.hits, *self.context]

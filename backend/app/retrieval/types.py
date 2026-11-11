from __future__ import annotations

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


class Retrieval(BaseModel):
    hits: list[Chunk]
    context: list[Chunk] = Field(default_factory=list)
    documents: list[DocumentMeta] = Field(default_factory=list)

    def passages(self) -> list[Chunk]:
        return [*self.hits, *self.context]

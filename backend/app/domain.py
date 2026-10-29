
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str
    article_number: int | None
    article_title: str
    section: str
    page_start: int | None
    page_end: int | None
    text: str
    source_url: str

class Claim(BaseModel):
    text: str
    passage_ids: list[str] = Field(min_length=1)

class DraftAnswer(BaseModel):

    claims: list[Claim] = Field(default_factory=list)
    insufficient_evidence: bool = False

class CitedAnswer(BaseModel):
    kind: Literal["answer"] = "answer"
    claims: list[Claim] = Field(min_length=1)

class Refusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: Literal["no_evidence", "citations_dropped"]
    message: str

CopilotResponse = Annotated[CitedAnswer | Refusal, Field(discriminator="kind")]

NO_EVIDENCE_MESSAGE = (
    "The retrieved passages from the 2023 NBA Collective Bargaining Agreement "
    "do not contain enough evidence to answer this."
)
CITATIONS_DROPPED_MESSAGE = (
    "Every claim cited a passage that was not in the retrieved set, "
    "so there is no answer to return."
)

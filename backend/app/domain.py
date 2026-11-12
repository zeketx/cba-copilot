
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


class DraftClaim(BaseModel):
    text: str
    quote: str
    passage_ids: list[str] = Field(min_length=1)

DraftStatus = Literal["answer", "insufficient_evidence", "ambiguous", "missing_inputs"]


class DraftAnswer(BaseModel):
    status: DraftStatus = "answer"
    claims: list[DraftClaim] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)

class CitedAnswer(BaseModel):
    kind: Literal["answer"] = "answer"
    claims: list[Claim] = Field(min_length=1)

class Refusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: Literal["no_evidence", "citations_dropped"]
    message: str


class Clarification(BaseModel):
    kind: Literal["clarification"] = "clarification"
    reason: Literal["ambiguous", "missing_inputs"]
    message: str
    claims: list[Claim] = Field(min_length=1)

CopilotResponse = Annotated[CitedAnswer | Refusal | Clarification, Field(discriminator="kind")]

NO_EVIDENCE_MESSAGE = (
    "The retrieved passages from the 2023 NBA Collective Bargaining Agreement "
    "do not contain enough evidence to answer this."
)
CITATIONS_DROPPED_MESSAGE = (
    "Every claim cited a passage that was not in the retrieved set, "
    "or a quote that was not in a cited passage, so there is no answer to return."
)
AMBIGUOUS_MESSAGE = (
    "More than one retrieved passage applies, and none says which one controls. "
    "Which season or effective date do you mean?"
)

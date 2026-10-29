from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from pydantic_ai import Agent

from app.domain import Chunk, Claim, DraftAnswer
from app.retrieval.aliases import expand_query
from app.retrieval.text import tokens

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

_INSTRUCTIONS = Path(__file__).with_name("instructions.md").read_text(encoding="utf-8")


class Drafter(Protocol):
    def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer: ...


def format_passages(question: str, passages: list[Chunk]) -> str:
    blocks = [f"Question: {question}", "Retrieved passages:"]
    if not passages:
        blocks.append("None.")
        return "\n".join(blocks)
    for passage in passages:
        blocks.append(
            f"[{passage.id}] Article {passage.article_number} Section {passage.section}\n"
            f"{passage.text}"
        )
    return "\n\n".join(blocks)


STRONG_OVERLAP = 4


def _in_citation_band(score: int, best: int) -> bool:
    return score == best or (best - score == 1 and score >= STRONG_OVERLAP)


class OverlapDrafter:
    def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer:
        query_tokens = tokens(expand_query(question))
        ranked: list[tuple[int, Chunk]] = []
        for passage in passages:
            haystack = tokens(f"{passage.text} {passage.section} {passage.article_title}")
            overlap = len(query_tokens & haystack)
            if overlap >= 2:
                ranked.append((overlap, passage))
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        if not ranked:
            return DraftAnswer(claims=[], insufficient_evidence=True)
        best = ranked[0][0]
        chosen = [
            passage for score, passage in ranked if _in_citation_band(score, best)
        ]
        claims = [Claim(text=passage.text.strip(), passage_ids=[passage.id]) for passage in chosen]
        return DraftAnswer(claims=claims)


class AgentDrafter:
    def __init__(self, agent: Agent[None, DraftAnswer]) -> None:
        self._agent = agent

    def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer:
        result = self._agent.run_sync(format_passages(question, passages))
        return result.output


def build_agent(model: object) -> Agent[None, DraftAnswer]:
    return Agent(model, output_type=DraftAnswer, instructions=_INSTRUCTIONS)


def refuse_live_model(model_name: str) -> None:
    raise RuntimeError(
        f"Live model {model_name} is disabled in this skeleton. "
        "Add credits and remove this guard before a live run."
    )

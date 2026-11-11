from __future__ import annotations

import os
import re
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
_SEASON = re.compile(r"\b20\d{2}-\d{2}\b", re.IGNORECASE)
_EFFECTIVE = re.compile(r"\beffective date\b(?:\s+\S+){0,6}", re.IGNORECASE)
_ASKS_FOR_RESULT = re.compile(
    r"\b(?:how much|dollar|dollars|calculate|calculation)\b",
    re.IGNORECASE,
)
_PERCENT_OF = re.compile(
    r"\bpercent of\s+(?:the\s+|his\s+|her\s+|a\s+)?(?:player's\s+)?"
    r"(?P<input>[a-z][a-z\- ]{2,80}?)(?=\s*(?:,|\.| or |$))",
    re.IGNORECASE,
)
_DIGIT = re.compile(r"\d")
CLARIFYING_QUESTION = "Which season or effective date applies?"


def _in_citation_band(score: int, best: int) -> bool:
    return score == best or (best - score == 1 and score >= STRONG_OVERLAP)


def _date_markers(text: str) -> set[str]:
    found = {match.group(0).lower() for match in _SEASON.finditer(text)}
    for match in _EFFECTIVE.finditer(text):
        found.add(" ".join(match.group(0).lower().split()))
    return found


def _operation_inputs(text: str) -> list[str]:
    names: list[str] = []
    for match in _PERCENT_OF.finditer(text):
        name = " ".join(match.group("input").lower().split())
        if name and name not in names:
            names.append(name)
    return names


def _missing_text(names: list[str]) -> str:
    labeled = [f"the {name}" for name in names]
    if len(labeled) == 1:
        joined = labeled[0]
        verb = "is"
    elif len(labeled) == 2:
        joined = f"{labeled[0]} and {labeled[1]}"
        verb = "are"
    else:
        joined = ", ".join(labeled[:-1]) + f", and {labeled[-1]}"
        verb = "are"
    return f"{joined[0].upper()}{joined[1:]} {verb} missing, so there is no computed number."


def _for_named_date(question: str, chosen: list[Chunk]) -> list[Chunk]:
    named = _date_markers(question)
    if not named:
        return chosen
    matched = [passage for passage in chosen if _date_markers(passage.text) & named]
    return matched or chosen


def _ambiguous_passages(question: str, chosen: list[Chunk]) -> list[Chunk]:
    if _date_markers(question):
        return []
    dated = [passage for passage in chosen if _date_markers(passage.text)]
    marker_sets = {frozenset(_date_markers(passage.text)) for passage in dated}
    if len(dated) >= 2 and len(marker_sets) >= 2:
        return dated
    return []


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
        chosen = _for_named_date(
            question,
            [passage for score, passage in ranked if _in_citation_band(score, best)],
        )
        ambiguous = _ambiguous_passages(question, chosen)
        if ambiguous:
            return DraftAnswer(
                kind="ambiguous",
                question=CLARIFYING_QUESTION,
                passage_ids=[passage.id for passage in ambiguous],
            )
        if _ASKS_FOR_RESULT.search(question) and _DIGIT.search(question) is None:
            for passage in chosen:
                names = _operation_inputs(passage.text)
                if not names:
                    continue
                text = _missing_text(names)
                if _DIGIT.search(text):
                    continue
                return DraftAnswer(
                    kind="missing_inputs",
                    text=text,
                    passage_ids=[passage.id],
                )
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

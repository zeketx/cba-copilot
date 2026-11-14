from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.config import Settings
from app.domain import Chunk, DraftAnswer, DraftClaim
from app.retrieval.aliases import expand_query
from app.retrieval.text import tokens

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

_INSTRUCTIONS = Path(__file__).with_name("instructions.md").read_text(encoding="utf-8")
DEFAULT_ANSWER_MAX_TOKENS = 16384
_MAX_PASSAGE_CHARS = 4_000
_MAX_PROMPT_CHARS = 48_000


class Drafter(Protocol):
    def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer: ...


def _clip_passage_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].rstrip()
    return f"{clipped}…"


def format_passages(question: str, passages: list[Chunk]) -> str:
    blocks = [f"Question: {question}", "Retrieved passages:"]
    if not passages:
        blocks.append("None.")
        return "\n".join(blocks)
    used = 0
    for passage in passages:
        body = _clip_passage_text(passage.text, _MAX_PASSAGE_CHARS)
        block = (
            f"[{passage.id}] Article {passage.article_number} Section {passage.section}\n"
            f"{body}"
        )
        extra = len(block) + (2 if used else 0)
        if used and used + extra > _MAX_PROMPT_CHARS:
            break
        blocks.append(block)
        used += extra
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
            return DraftAnswer(status="insufficient_evidence")
        best = ranked[0][0]
        chosen = [
            passage for score, passage in ranked if _in_citation_band(score, best)
        ]
        claims = [
            DraftClaim(
                text=passage.text.strip(),
                quote=passage.text.strip(),
                passage_ids=[passage.id],
            )
            for passage in chosen
        ]
        return DraftAnswer(claims=claims)


class AgentDrafter:
    def __init__(self, agent: Agent[None, DraftAnswer]) -> None:
        self._agent = agent

    def draft(self, question: str, passages: list[Chunk]) -> DraftAnswer:
        result = self._agent.run_sync(format_passages(question, passages))
        return result.output


def build_agent(
    model: object,
    *,
    max_tokens: int = DEFAULT_ANSWER_MAX_TOKENS,
) -> Agent[None, DraftAnswer]:
    return Agent(
        model,
        output_type=DraftAnswer,
        instructions=_INSTRUCTIONS,
        model_settings={"temperature": 0, "timeout": 60, "max_tokens": max_tokens},
    )


def _openai_model(name: str, settings: Settings) -> Model:
    return OpenAIChatModel(name, provider=OpenAIProvider(api_key=settings.openai_api_key))


def _google_model(name: str, settings: Settings) -> Model:
    return GoogleModel(name, provider=GoogleProvider(api_key=settings.gemini_api_key))


def _openrouter_model(name: str, settings: Settings) -> Model:
    return OpenAIChatModel(name, provider=OpenRouterProvider(api_key=settings.openrouter_api_key))


_LIVE_MODELS: dict[str, Callable[[str, Settings], Model]] = {
    "openai": _openai_model,
    "google": _google_model,
    "openrouter": _openrouter_model,
}


def build_live_model(settings: Settings) -> Model:
    name = settings.answer_model_id.split(":", 1)[-1]
    return _LIVE_MODELS[settings.answer_provider](name, settings)


def build_live_drafter(settings: Settings) -> AgentDrafter:
    return AgentDrafter(
        build_agent(build_live_model(settings), max_tokens=settings.answer_max_tokens)
    )

from __future__ import annotations

import re

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.text import STOPWORDS

_WORD_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _words(text: str) -> list[str]:
    found = [match.group(0) for match in _WORD_RE.finditer(text.lower())]
    return [word for word in found if len(word) > 2 and word not in STOPWORDS]


def query_phrases(question: str) -> list[str]:
    """Long content phrases from the expanded question, longest first.

    Unhyphenated bigrams like "salary cap" are skipped; they match too much of
    the agreement. A hyphenated bigram such as "two-way contract" is kept.
    """
    words = _words(expand_query(question))
    phrases: list[str] = []
    seen: set[str] = set()
    for size in range(min(6, len(words)), 1, -1):
        for start in range(len(words) - size + 1):
            parts = words[start : start + size]
            if size == 2 and not any("-" in part for part in parts):
                continue
            phrase = " ".join(parts)
            if phrase in seen:
                continue
            seen.add(phrase)
            phrases.append(phrase)
    return phrases


def _boundary_match(haystack: str, phrase: str) -> bool:
    pattern = rf"(?<![a-z0-9-]){re.escape(phrase)}(?![a-z0-9-])"
    return re.search(pattern, haystack) is not None


def phrase_score(chunk: Chunk, phrases: list[str]) -> int:
    section = f"{chunk.section} {chunk.article_title}".lower()
    body = chunk.text.lower()
    score = 0
    for phrase in phrases:
        if _boundary_match(section, phrase):
            score += 3 * len(phrase.split())
        elif _boundary_match(body, phrase):
            score += len(phrase.split())
    return score


def phrase_ranks(question: str, chunks: list[Chunk]) -> list[str]:
    phrases = query_phrases(question)
    if not phrases:
        return []
    scored = [(phrase_score(chunk, phrases), index, chunk.id) for index, chunk in enumerate(chunks)]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk_id for _score, _index, chunk_id in scored]

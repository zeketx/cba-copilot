from __future__ import annotations

import re

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.text import STOPWORDS

_WORD_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _words(text: str) -> list[str]:
    found = [match.group(0) for match in _WORD_RE.finditer(text.lower())]
    return [word for word in found if len(word) > 2 and word not in STOPWORDS]


_FLOODING_BIGRAMS = frozenset(
    {
        "salary cap",
        "player contract",
        "this agreement",
        "cap year",
        "team salary",
        "salary mean",
    }
)


def query_phrases(question: str) -> list[str]:
    """Long content phrases from the expanded question, longest first.

    A hyphenated bigram such as "two-way contract" is kept. An unhyphenated
    bigram is kept unless it is a flooding pair such as "salary cap".
    """
    words = _words(expand_query(question))
    phrases: list[str] = []
    seen: set[str] = set()
    for size in range(min(6, len(words)), 1, -1):
        for start in range(len(words) - size + 1):
            parts = words[start : start + size]
            phrase = " ".join(parts)
            if (
                size == 2
                and not any("-" in part for part in parts)
                and phrase in _FLOODING_BIGRAMS
            ):
                continue
            if phrase in seen:
                continue
            seen.add(phrase)
            phrases.append(phrase)
    return phrases


_WHITESPACE = re.compile(r"\s+")
_NOISE = re.compile(r"[^a-z0-9\s-]+")
_PAREN_AMOUNT = re.compile(r"\(\s*[\d.,]+\s*%?\s*\)")


def _fold_ws(text: str) -> str:
    cleaned = _PAREN_AMOUNT.sub(" ", text.lower())
    return _WHITESPACE.sub(" ", _NOISE.sub(" ", cleaned)).strip()


def _s_variants(word: str) -> tuple[str, ...]:
    if len(word) <= 3 or word.endswith("ss") or "-" in word:
        return (word,)
    if word.endswith("s"):
        return (word, word[:-1])
    return (word, word + "s")


def _phrase_variants(phrase: str) -> list[str]:
    """Match a query phrase to a one-letter plural/singular difference.

    "salary mean" should still hit the CBA line that says "Salary means".
    """
    words = _fold_ws(phrase).split()
    variants = [phrase]
    seen = {phrase}
    for index, word in enumerate(words):
        for alt in _s_variants(word):
            if alt == word:
                continue
            candidate = " ".join([*words[:index], alt, *words[index + 1 :]])
            if candidate not in seen:
                seen.add(candidate)
                variants.append(candidate)
    return variants


def _boundary_match(haystack: str, phrase: str) -> bool:
    folded = _fold_ws(haystack)
    for variant in _phrase_variants(phrase):
        pattern = rf"(?<![a-z0-9-]){re.escape(_fold_ws(variant))}(?![a-z0-9-])"
        if re.search(pattern, folded) is not None:
            return True
    return False


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

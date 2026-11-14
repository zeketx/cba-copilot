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


_WORD_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


def _phrase_needles(phrases: list[str]) -> list[tuple[int, tuple[str, ...]]]:
    needles: list[tuple[int, tuple[str, ...]]] = []
    for phrase in phrases:
        seen: set[str] = set()
        variants: list[str] = []
        for variant in _phrase_variants(phrase):
            folded = _fold_ws(variant)
            if not folded or folded in seen:
                continue
            seen.add(folded)
            variants.append(folded)
        if variants:
            needles.append((len(phrase.split()), tuple(variants)))
    return needles


def _boundary_find(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    start = 0
    length = len(needle)
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return False
        left = index == 0 or haystack[index - 1] not in _WORD_CHARS
        end = index + length
        right = end == len(haystack) or haystack[end] not in _WORD_CHARS
        if left and right:
            return True
        start = index + 1


def _has_phrase(haystack: str, variants: tuple[str, ...]) -> bool:
    return any(_boundary_find(haystack, variant) for variant in variants)


def _score_folded(
    section: str, body: str, needles: list[tuple[int, tuple[str, ...]]]
) -> int:
    score = 0
    for words, variants in needles:
        if _has_phrase(section, variants):
            score += 3 * words
        elif _has_phrase(body, variants):
            score += words
    return score


def phrase_score(chunk: Chunk, phrases: list[str]) -> int:
    return _score_folded(
        _fold_ws(f"{chunk.section} {chunk.article_title}"),
        _fold_ws(chunk.text),
        _phrase_needles(phrases),
    )


def phrase_ranks(question: str, chunks: list[Chunk]) -> list[str]:
    phrases = query_phrases(question)
    if not phrases:
        return []
    needles = _phrase_needles(phrases)
    scored: list[tuple[int, int, str]] = []
    for index, chunk in enumerate(chunks):
        score = _score_folded(
            _fold_ws(f"{chunk.section} {chunk.article_title}"),
            _fold_ws(chunk.text),
            needles,
        )
        if score:
            scored.append((score, index, chunk.id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk_id for _score, _index, chunk_id in scored]

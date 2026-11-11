from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain import Chunk

_ID_CHARS = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


@dataclass(frozen=True)
class ExpectedSection:
    article: int
    section_contains: str


@dataclass(frozen=True)
class BenchQuestion:
    id: str
    question: str
    match: str
    draft: bool
    expected: tuple[ExpectedSection, ...]


@dataclass(frozen=True)
class RankMetrics:
    recall_at_5: float
    recall_at_8: float
    mrr: float


def section_matches(section: str, needle: str) -> bool:
    if not needle:
        return False
    start = 0
    while True:
        index = section.find(needle, start)
        if index < 0:
            return False
        before = section[index - 1 : index]
        after = section[index + len(needle) : index + len(needle) + 1]
        before_ok = before == "" or before not in _ID_CHARS
        after_ok = after == "" or after not in _ID_CHARS
        if before_ok and after_ok:
            return True
        start = index + 1


def chunk_matches(chunk: Chunk, expected: ExpectedSection) -> bool:
    return chunk.article_number == expected.article and section_matches(
        chunk.section,
        expected.section_contains,
    )


def first_relevant_rank(chunks: list[Chunk], question: BenchQuestion) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if any(chunk_matches(chunk, expected) for expected in question.expected):
            return rank
    return None


def recall_at(chunks: list[Chunk], question: BenchQuestion, k: int) -> float:
    if not question.expected:
        return 0.0
    top = chunks[:k]
    hits = [
        any(chunk_matches(chunk, expected) for chunk in top) for expected in question.expected
    ]
    if question.match == "any":
        return 1.0 if any(hits) else 0.0
    return sum(1.0 for hit in hits if hit) / len(hits)


def mean_reciprocal_rank(chunks: list[Chunk], question: BenchQuestion) -> float:
    rank = first_relevant_rank(chunks, question)
    if rank is None:
        return 0.0
    return 1.0 / rank


def aggregate(questions: list[BenchQuestion], rankings: dict[str, list[Chunk]]) -> RankMetrics:
    if not questions:
        return RankMetrics(recall_at_5=0.0, recall_at_8=0.0, mrr=0.0)
    recall_5 = 0.0
    recall_8 = 0.0
    mrr = 0.0
    for question in questions:
        ranked = rankings[question.id]
        recall_5 += recall_at(ranked, question, 5)
        recall_8 += recall_at(ranked, question, 8)
        mrr += mean_reciprocal_rank(ranked, question)
    count = len(questions)
    return RankMetrics(
        recall_at_5=recall_5 / count,
        recall_at_8=recall_8 / count,
        mrr=mrr / count,
    )


def percentile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("percentile needs at least one value")
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    ordered = sorted(values)
    rank = math.ceil(percent / 100 * len(ordered))
    index = min(len(ordered), max(rank, 1)) - 1
    return ordered[index]

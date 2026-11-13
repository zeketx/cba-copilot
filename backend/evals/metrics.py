from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.domain import Chunk

_ID_CHARS = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


@dataclass(frozen=True)
class ExpectedSection:
    article: int | None
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


_DB_SECTION = re.compile(r"^(?P<num>\d+)\.\s+.+?\s+/\s+(?P<rest>.+)$", re.DOTALL)
_LEADING_MARKERS = re.compile(r"^(?P<markers>(?:\([A-Za-z0-9]+\)\s*)+)(?P<tail>.*)$", re.DOTALL)
_PLAIN_SECTION = re.compile(r"^(?P<num>\d+)\.\s+(?P<title>.*)$", re.DOTALL)


def section_for_match(section: str) -> str:
    """Fold an ingest label into the string `section_matches` already searches.

    Ingest stores `1. Definitions / (yy) “Qualifying…”`. The questions say `1(yy)`.
    A heading that spaces its markers, `(e) (1)`, is also kept so `8(e) (1)` still hits.
    A label that is already `1(yy)` or `6(b)(1)` is returned unchanged.
    """
    stripped = section.strip()
    slash = _DB_SECTION.match(stripped)
    if slash:
        number = slash.group("num")
        rest = slash.group("rest").strip()
        markers = _LEADING_MARKERS.match(rest)
        if markers is None:
            return f"{number} {rest}".strip()
        raw = markers.group("markers").rstrip()
        tail = markers.group("tail").lstrip()
        compact = re.sub(r"\s+", "", raw)
        primary = f"{number}{compact}"
        text = f"{primary} {tail}".strip() if tail else primary
        spaced = f"{number}{raw}"
        if spaced != primary:
            extra = f"{spaced} {tail}".strip() if tail else spaced
            text = f"{text} {extra}"
        return text
    plain = _PLAIN_SECTION.match(stripped)
    if plain:
        return f"{plain.group('num')} {plain.group('title')}".strip()
    return stripped


_PAREN_SPACE = re.compile(r"\)\s+\(")


def compact_parentheticals(value: str) -> str:
    """Join `(e) (1)` into `(e)(1)` so a compact label still matches a spaced needle."""
    return _PAREN_SPACE.sub(")(", value)


def section_matches(section: str, needle: str) -> bool:
    if not needle:
        return False
    if _section_find(section, needle):
        return True
    compact_needle = compact_parentheticals(needle)
    if compact_needle != needle and _section_find(section, compact_needle):
        return True
    compact_section = compact_parentheticals(section)
    if compact_section != section and _section_find(compact_section, compact_needle):
        return True
    return False


def _section_find(section: str, needle: str) -> bool:
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
        section_for_match(chunk.section),
        expected.section_contains,
    )


_NEEDLE_NUMBER = re.compile(r"^(?P<num>\d+)")
_NEEDLE_GROUP = re.compile(r"\(\s*(?P<token>[A-Za-z0-9]+)\s*\)")


def normalize_label(value: str) -> str:
    """Lowercase a label and join letters that a PDF split with a space.

    `V eteran` and `Agen t` become `veteran` and `agent`. A space between two
    longer words stays, so `Free Agent` does not become one word.
    """
    lowered = value.lower()
    pieces: list[str] = []
    index = 0
    while index < len(lowered):
        if not lowered[index].isspace():
            pieces.append(lowered[index])
            index += 1
            continue
        end = index
        while end < len(lowered) and lowered[end].isspace():
            end += 1
        before = _letter_run_ending_at(lowered, index)
        after = _letter_run_starting_at(lowered, end)
        if before and after and (len(before) == 1 or len(after) == 1):
            index = end
            continue
        pieces.append(" ")
        index = end
    return "".join(pieces).strip()


def _letter_run_ending_at(value: str, index: int) -> str:
    end = index
    while end > 0 and value[end - 1].isalpha():
        end -= 1
    return value[end:index]


def _letter_run_starting_at(value: str, index: int) -> str:
    end = index
    while end < len(value) and value[end].isalpha():
        end += 1
    return value[index:end]


def _letter_run(token: str) -> bool:
    return re.fullmatch(r"([A-Za-z])\1*", token) is not None


def needle_parent(needle: str) -> tuple[str, tuple[str, ...]] | None:
    """Return the section-and-letter prefix and the later parenthetical markers.

    `6(e)(1)` yields `6(e)` and `(1)`. `6(j)(1)(i)` yields `6(j)`, `(1)`, and `(i)`.
    A needle with no later marker, such as `6(b) Veteran` or `1(yy)`, returns None.
    A parent label alone is not a hit.
    """
    stripped = needle.strip()
    head = _NEEDLE_NUMBER.match(stripped)
    if head is None:
        return None
    rest = stripped[head.end() :]
    groups = list(_NEEDLE_GROUP.finditer(rest))
    if not groups or rest[: groups[0].start()].strip():
        return None
    first = groups[0].group("token")
    if not _letter_run(first):
        return None
    markers: list[str] = []
    cursor = groups[0].end()
    for group in groups[1:]:
        if rest[cursor : group.start()].strip():
            break
        markers.append(f"({group.group('token')})")
        cursor = group.end()
    if not markers:
        return None
    return f"{head.group('num')}({first.lower()})", tuple(markers)


def text_has_marker(text: str, marker: str) -> bool:
    token = marker[1:-1]
    return re.search(r"\(\s*" + re.escape(token) + r"\s*\)", text) is not None


def _label_is_parent(section: str, parent: str) -> bool:
    folded = normalize_label(section_for_match(section))
    head = normalize_label(parent)
    if not folded.startswith(head):
        return False
    if len(folded) == len(head):
        return True
    return folded[len(head)] not in _ID_CHARS


def lenient_chunk_matches(chunk: Chunk, expected: ExpectedSection) -> bool:
    if chunk.article_number != expected.article:
        return False
    mapped = section_for_match(chunk.section)
    needle = expected.section_contains
    if section_matches(normalize_label(mapped), normalize_label(needle)):
        return True
    parent = needle_parent(needle)
    if parent is None:
        return False
    prefix, markers = parent
    if not _label_is_parent(chunk.section, prefix):
        return False
    return all(text_has_marker(chunk.text, marker) for marker in markers)


def first_relevant_rank(
    chunks: list[Chunk],
    question: BenchQuestion,
    *,
    matches=chunk_matches,
) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if any(matches(chunk, expected) for expected in question.expected):
            return rank
    return None


def recall_at(
    chunks: list[Chunk],
    question: BenchQuestion,
    k: int,
    *,
    matches=chunk_matches,
) -> float:
    if not question.expected:
        return 0.0
    top = chunks[:k]
    hits = [any(matches(chunk, expected) for chunk in top) for expected in question.expected]
    if question.match == "any":
        return 1.0 if any(hits) else 0.0
    return sum(1.0 for hit in hits if hit) / len(hits)


def mean_reciprocal_rank(
    chunks: list[Chunk],
    question: BenchQuestion,
    *,
    matches=chunk_matches,
) -> float:
    rank = first_relevant_rank(chunks, question, matches=matches)
    if rank is None:
        return 0.0
    return 1.0 / rank


def aggregate(
    questions: list[BenchQuestion],
    rankings: dict[str, list[Chunk]],
    *,
    matches=chunk_matches,
) -> RankMetrics:
    if not questions:
        return RankMetrics(recall_at_5=0.0, recall_at_8=0.0, mrr=0.0)
    recall_5 = 0.0
    recall_8 = 0.0
    mrr = 0.0
    for question in questions:
        ranked = rankings[question.id]
        recall_5 += recall_at(ranked, question, 5, matches=matches)
        recall_8 += recall_at(ranked, question, 8, matches=matches)
        mrr += mean_reciprocal_rank(ranked, question, matches=matches)
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

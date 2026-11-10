from __future__ import annotations

import re
from dataclasses import dataclass

from ingest.chunker import chunk_markdown, roman_to_int

_ART = r"(?:Article)\s+([IVXLCDM]+|\d+)"
_SEC = r"(?:Section)\s+(\d+(?:\([a-z0-9]+\))*)"
_ART_SEC = re.compile(rf"{_ART}\s*,\s*{_SEC}", re.IGNORECASE)
_SEC_ART = re.compile(rf"{_SEC}\s+of\s+{_ART}", re.IGNORECASE)
_SEC_THIS = re.compile(rf"{_SEC}\s+of\s+this\s+Article", re.IGNORECASE)
_SEC_BELOW = re.compile(rf"{_SEC}\s+(?:below|above)", re.IGNORECASE)
_ART_ONLY = re.compile(rf"{_ART}\b", re.IGNORECASE)
_SEC_BARE = re.compile(_SEC, re.IGNORECASE)
_OWN_SECTION = re.compile(r"(?:Section\s+)?(\d+(?:\([a-z0-9]+\))*)", re.IGNORECASE)


@dataclass(frozen=True)
class ChunkRow:
    chunk_index: int
    article_number: int | None
    article_title: str
    section: str
    page_start: int | None
    page_end: int | None
    printed_page: int | None
    viewer_page: int | None
    source_url: str
    text: str
    metadata: dict


def references(
    text: str, article_number: int | None, section_label: str
) -> list[dict]:
    own = _own_section(section_label)
    found: list[tuple[int, int, dict]] = []
    for match in _ART_SEC.finditer(text):
        found.append(
            (match.start(), match.end(), _ref(_article_int(match.group(1)), match.group(2)))
        )
    for match in _SEC_ART.finditer(text):
        found.append(
            (match.start(), match.end(), _ref(_article_int(match.group(2)), match.group(1)))
        )
    for match in _SEC_THIS.finditer(text):
        if article_number is None:
            continue
        found.append((match.start(), match.end(), _ref(article_number, match.group(1))))
    for match in _SEC_BELOW.finditer(text):
        if article_number is None:
            continue
        found.append((match.start(), match.end(), _ref(article_number, match.group(1))))
    for match in _ART_ONLY.finditer(text):
        found.append((match.start(), match.end(), _ref(_article_int(match.group(1)), None)))
    for match in _SEC_BARE.finditer(text):
        if article_number is None:
            continue
        found.append((match.start(), match.end(), _ref(article_number, match.group(1))))
    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    seen: set[tuple[int, str | None]] = set()
    ordered: list[dict] = []
    cursor = 0
    for start, end, item in found:
        if start < cursor:
            continue
        cursor = end
        section = item.get("section")
        if isinstance(section, str) and own is not None and _same_section(section, own):
            continue
        if section is None and article_number is not None and item["article"] == article_number:
            continue
        key = (item["article"], section)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def chunk_rows(markdown: str, source_url: str, offset: int) -> list[ChunkRow]:
    chunks = chunk_markdown(markdown, source_url=source_url)
    rows: list[ChunkRow] = []
    for index, chunk in enumerate(chunks):
        printed_start = None if chunk.page_start is None else chunk.page_start - offset
        printed_end = None if chunk.page_end is None else chunk.page_end - offset
        rows.append(
            ChunkRow(
                chunk_index=index,
                article_number=chunk.article_number,
                article_title=chunk.article_title,
                section=chunk.section,
                page_start=printed_start,
                page_end=printed_end,
                printed_page=printed_start,
                viewer_page=chunk.page_start,
                source_url=chunk.source_url,
                text=chunk.text,
                metadata={
                    "slug": chunk.id,
                    "references": references(chunk.text, chunk.article_number, chunk.section),
                },
            )
        )
    return rows


def _article_int(token: str) -> int:
    if token.isdigit():
        return int(token)
    return roman_to_int(token)


def _ref(article: int, section: str | None) -> dict:
    if section is None:
        return {"article": article}
    return {"article": article, "section": section}


def _own_section(section_label: str) -> str | None:
    match = _OWN_SECTION.match(section_label.strip())
    if match is None:
        return None
    return match.group(1)


def _same_section(referenced: str, own: str) -> bool:
    return referenced == own

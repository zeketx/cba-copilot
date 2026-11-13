from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

_ARTICLE_ODD = re.compile(r"^Article\s+[IVXLCDM]+\s+(\d+)$")
_ARTICLE_EVEN = re.compile(r"^(\d+)\s+Article\s+[IVXLCDM]+$")
_EXHIBIT_LEADING = re.compile(r"^Exhibit\s+\S+\s+(\S+)$")
_EXHIBIT_TRAILING = re.compile(r"^(\S+)\s+Exhibit\s+\S+$")
_ARTICLE_OPEN = re.compile(r"^ARTICLE\s+([IVXLCDM]+)$")
_SECTION_OPEN = re.compile(r"^Section\s+(\d+)\.\s+(.+)$")
_SPACE_BEFORE_HYPHEN = re.compile(r"(?<=\w) -(?=\w)")
_SPACE_AFTER_HYPHEN = re.compile(r"(?<=\w)- (?!(?:and|or|through|to)\b)(?=\w)")


@dataclass(frozen=True)
class PdfPage:
    viewer: int
    printed: str | None
    body: str


def read_pages(path: Path | str) -> list[PdfPage]:
    reader = PdfReader(path)
    pages: list[PdfPage] = []
    for index, page in enumerate(reader.pages):
        raw = page.extract_text() or ""
        pages.append(split_header(index + 1, join_hyphens(raw)))
    return pages


def join_hyphens(text: str) -> str:
    """Drop the space pypdf puts beside a joined hyphen, as in `Mid -Level` or `Two- Way`.

    A suspended hyphen before `and`, `or`, `through`, or `to` keeps its space,
    as in `Team- or League-related`.
    """
    return _SPACE_AFTER_HYPHEN.sub("-", _SPACE_BEFORE_HYPHEN.sub("-", text))


def split_header(viewer: int, raw_text: str) -> PdfPage:
    lines = raw_text.splitlines()
    header_at = next((index for index, line in enumerate(lines) if line.strip()), None)
    if header_at is None:
        return PdfPage(viewer=viewer, printed=None, body="")
    header = lines[header_at].strip()
    body = "\n".join(lines[header_at + 1 :])
    return PdfPage(viewer=viewer, printed=_printed_label(header), body=body)


def measure_offset(pages: list[PdfPage]) -> int:
    by_offset: dict[int, list[int]] = {}
    for page in pages:
        if page.printed is None or not page.printed.isdigit():
            continue
        offset = page.viewer - int(page.printed)
        by_offset.setdefault(offset, []).append(page.viewer)
    if not by_offset:
        raise ValueError("no Article header with a numeric printed page")
    majority = max(by_offset, key=lambda offset: (len(by_offset[offset]), -offset))
    disagreeing = sorted(
        viewer
        for offset, viewers in by_offset.items()
        if offset != majority
        for viewer in viewers
    )
    if disagreeing:
        raise ValueError(f"page offset disagrees on viewer pages {disagreeing}")
    return majority


def render_markdown(pages: list[PdfPage]) -> str:
    lines: list[str] = []
    pending_roman: str | None = None
    next_section = 1
    for page in pages:
        if page.printed is None:
            continue
        if not page.printed.isdigit():
            break
        lines.append(f"<!-- pdf-page: {page.viewer} -->")
        for raw in page.body.splitlines():
            stripped = raw.strip()
            if pending_roman is not None:
                if not stripped:
                    continue
                lines.append(f"# Article {pending_roman}. {stripped}")
                pending_roman = None
                continue
            opened = _ARTICLE_OPEN.match(stripped)
            if opened:
                pending_roman = opened.group(1)
                next_section = 1
                continue
            section = _SECTION_OPEN.match(stripped)
            if section and int(section.group(1)) == next_section:
                title = section.group(2).rstrip()
                if title.endswith("."):
                    title = title[:-1]
                lines.append(f"## Section {section.group(1)}. {title}")
                next_section += 1
                continue
            lines.append(raw)
    if pending_roman is not None:
        lines.append(f"# Article {pending_roman}.")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _printed_label(header: str) -> str | None:
    if "table of contents" in header.lower():
        return None
    odd = _ARTICLE_ODD.fullmatch(header)
    if odd:
        return odd.group(1)
    even = _ARTICLE_EVEN.fullmatch(header)
    if even:
        return even.group(1)
    exhibit = _EXHIBIT_LEADING.fullmatch(header) or _EXHIBIT_TRAILING.fullmatch(header)
    if exhibit:
        return exhibit.group(1)
    return None

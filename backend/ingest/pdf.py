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
_EXHIBIT_OPEN = re.compile(r"^EXHIBIT\s+([A-Z][A-Z0-9-]*)$")
_EXHIBIT_NUMBERED = re.compile(r"^(\d+)\.\s+(.+)$")
_EXHIBIT_LETTER = re.compile(r"^([A-Z])\.\s+(.+)$")
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
    pending_exhibit_title = False
    for page in pages:
        if page.printed is None:
            continue
        printed_attr = f" printed: {page.printed}"
        lines.append(f"<!-- pdf-page: {page.viewer}{printed_attr} -->")
        if not page.printed.isdigit():
            pending_roman = None
            pending_exhibit_title = False
            for raw in page.body.splitlines():
                stripped = raw.strip()
                opened = _EXHIBIT_OPEN.match(stripped)
                if opened:
                    if pending_exhibit_title:
                        pending_exhibit_title = False
                    lines.append(f"# Exhibit {opened.group(1)}")
                    pending_exhibit_title = True
                    continue
                if pending_exhibit_title and not stripped:
                    continue
                if pending_exhibit_title and (
                    _exhibit_numbered_heading(stripped) is not None
                    or _exhibit_letter_heading(stripped) is not None
                ):
                    pending_exhibit_title = False
                elif pending_exhibit_title and _is_exhibit_title_line(stripped):
                    last = lines[-1]
                    suffix = (
                        last.split(".", 1)[1].strip()
                        if last.startswith("# Exhibit") and ". " in last
                        else ""
                    )
                    addition = _title_case_heading(stripped)
                    if suffix:
                        lines[-1] = f"{last.split('.', 1)[0]}. {suffix} {addition}"
                    else:
                        lines[-1] = f"{last}. {addition}"
                    continue
                pending_exhibit_title = False
                numbered = _exhibit_numbered_heading(stripped)
                if numbered is not None:
                    number, title = numbered
                    lines.append(f"## {number}. {title}")
                    continue
                lettered = _exhibit_letter_heading(stripped)
                if lettered is not None:
                    letter, title = lettered
                    lines.append(f"## {letter}. {title}")
                    continue
                lines.append(raw)
            continue
        pending_exhibit_title = False
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


def _is_all_caps_title(line: str) -> bool:
    if not line or len(line) > 80 or not line[0].isalpha():
        return False
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def _title_case_heading(value: str) -> str:
    keep = {"NBA", "NBPA", "BRI", "UPC", "CBA", "NHL"}
    words = []
    for word in value.split():
        pieces = []
        for part in re.split(r"([/-])", word):
            if part in {"/", "-"}:
                pieces.append(part)
                continue
            bare = part.strip(",;:")
            if bare.upper() in keep:
                pieces.append(part.upper())
            else:
                pieces.append(part.capitalize() if part else part)
        words.append("".join(pieces))
    return " ".join(words)


def _is_exhibit_title_line(line: str) -> bool:
    if _exhibit_numbered_heading(line) is not None or _exhibit_letter_heading(line) is not None:
        return False
    if not (_is_all_caps_title(line) or _is_title_case_heading(line)):
        return False
    return len(line.split()) <= 8


def _mostly_upper(title: str) -> bool:
    letters = [char for char in title if char.isalpha()]
    if len(letters) < 3:
        return False
    return sum(char.isupper() for char in letters) / len(letters) >= 0.85


def _exhibit_numbered_heading(line: str) -> tuple[str, str] | None:
    match = _EXHIBIT_NUMBERED.match(line)
    if match is None:
        return None
    title = match.group(2).rstrip(".").strip()
    if len(title) > 80 or not _mostly_upper(title):
        return None
    return match.group(1), _title_case_heading(title)


def _exhibit_letter_heading(line: str) -> tuple[str, str] | None:
    match = _EXHIBIT_LETTER.match(line)
    if match is None:
        return None
    title = match.group(2).strip()
    if len(title) > 80 or title.endswith("."):
        return None
    # Lists of drug names are single tokens; section titles have spaces.
    if " " not in title:
        return None
    return match.group(1), title


def _is_title_case_heading(line: str) -> bool:
    if not line or line.endswith(".") or line.endswith(":") or len(line) > 48:
        return False
    if line[0].isdigit() or line[0] in "([•-":
        return False
    words = [word for word in line.split() if word[0].isalpha()]
    if not 1 <= len(words) <= 6:
        return False
    skipped = {"a", "an", "the", "and", "or", "of", "on", "to", "for", "in"}
    return all(word[0].isupper() or word.lower() in skipped for word in words)


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

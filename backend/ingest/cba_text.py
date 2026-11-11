from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.domain import Chunk

from ingest.chunker import roman_to_int

_ARTICLE = re.compile(r"^ARTICLE\s+([IVXLCDM]+)\s*$")
_SECTION = re.compile(r"^Section\s+(\d+)\.\s*(.*)$")
_MARKER = re.compile(r"^(\s*)\(([a-z]+|\d+)\)\s+(\S.*)$")
_EXHIBIT = re.compile(r"^EXHIBIT\s+([A-Z][A-Z0-9-]*)\b\s*(.*)$")
_RUNNING_HEADER = re.compile(
    r"^(?:Article\s+[IVXLCDM]+\s+\d+|\d+\s+Article\s+[IVXLCDM]+|Exhibit\s+\S+\s+[A-Z0-9-]+)$",
    re.IGNORECASE,
)
_ROMAN_MARKERS = {
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
    "xiii",
    "xiv",
    "xv",
    "xvi",
    "xvii",
    "xviii",
    "xix",
    "xx",
}
_OPEN_QUOTES = set("\"'“‘")
_WRAPPED_CITATION_CHARS = 28


def read_pdf_layout(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("pdftotext is required to read the CBA PDF.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pdftotext failed for {path.name}.") from exc
    return completed.stdout.decode("utf-8", errors="replace")


def chunk_cba_text(text: str, *, source_url: str, page_offset: int = 24) -> list[Chunk]:
    parser = _CbaTextParser(source_url=source_url, page_offset=page_offset)
    pages = text.split("\f")
    for viewer, page in enumerate(pages, start=1):
        if parser.stopped:
            break
        parser.feed_page(viewer, page)
    parser.close()
    return parser.chunks()


def _marker_kind(token: str, *, definitions: bool, stack: list[tuple[str, str]]) -> str:
    if token.isdigit():
        return "number"
    if definitions and re.fullmatch(r"([a-z])\1*", token):
        return "letter"
    last_kind = stack[-1][0] if stack else ""
    last_letter = ""
    for kind, previous in stack:
        if kind == "letter":
            last_letter = previous
    if token in _ROMAN_MARKERS and last_kind in {"number", "roman"}:
        return "roman"
    if (
        len(token) == 1
        and len(last_letter) == 1
        and ord(token) == ord(last_letter) + 1
    ):
        return "letter"
    if token in _ROMAN_MARKERS:
        return "roman"
    return "letter"


def _apply_marker(stack: list[tuple[str, str]], kind: str, token: str) -> list[tuple[str, str]]:
    if kind == "letter":
        return [("letter", token)]
    if kind == "number":
        kept = [item for item in stack if item[0] == "letter"]
        return [*kept, ("number", token)]
    kept = [item for item in stack if item[0] in {"letter", "number"}]
    return [*kept, ("roman", token)]


def _short_heading(rest: str) -> str:
    cleaned = re.sub(r"\s+", " ", rest).strip()
    period = cleaned.find(".")
    if 0 <= period <= 90:
        cleaned = cleaned[:period]
    return cleaned[:80].strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "section"


def _wrapped_numeric_citation(token: str, rest: str) -> bool:
    if not token.isdigit():
        return False
    close = rest.find(")")
    return close != -1 and close < _WRAPPED_CITATION_CHARS


def _accept_marker(line: str) -> tuple[str, str] | None:
    match = _MARKER.match(line)
    if match is None:
        return None
    token = match.group(2).lower()
    if len(token) > 6:
        return None
    rest = match.group(3).strip()
    if _wrapped_numeric_citation(token, rest):
        return None
    if token.isdigit() and rest[0] not in _OPEN_QUOTES:
        words = re.findall(r"[A-Za-z0-9]+", rest)
        if len(words) < 3:
            return None
    if rest[0] not in _OPEN_QUOTES and rest[0] != "(" and not rest[0].isupper():
        return None
    return token, rest


class _Buffer:
    def __init__(self) -> None:
        self.article: int | None = None
        self.article_title = ""
        self.section = ""
        self.lines: list[tuple[int, str]] = []

    def clear(self) -> None:
        self.lines = []


class _CbaTextParser:
    def __init__(self, *, source_url: str, page_offset: int) -> None:
        self._source = source_url.split("#", 1)[0]
        self._page_offset = page_offset
        self._started = False
        self.stopped = False
        self._article: int | None = None
        self._article_title = ""
        self._section_number: str | None = None
        self._stack: list[tuple[str, str]] = []
        self._buffer = _Buffer()
        self._built: list[tuple[int | None, str, str, int, int, str]] = []
        self._in_exhibit = False

    def feed_page(self, viewer: int, page: str) -> None:
        lines = page.splitlines()
        skipped_header = False
        cleaned: list[str] = []
        for line in lines:
            if not skipped_header and line.strip():
                skipped_header = True
                if _RUNNING_HEADER.match(line.strip()):
                    continue
            cleaned.append(line)
        index = 0
        while index < len(cleaned):
            if self.stopped:
                return
            line = cleaned[index]
            stripped = line.strip()
            if not stripped:
                index += 1
                continue
            if not self._started:
                if _ARTICLE.match(stripped):
                    self._started = True
                else:
                    index += 1
                    continue
            exhibit = _EXHIBIT.match(stripped)
            if exhibit and (self._article is not None or self._in_exhibit):
                self._flush()
                self._begin_exhibit(exhibit.group(1), stripped, viewer)
                index += 1
                continue
            if self._in_exhibit:
                self._add(stripped, viewer)
                index += 1
                continue
            article = _ARTICLE.match(stripped)
            if article:
                self._begin_article(article.group(1), cleaned, index, viewer)
                index = self._cursor
                continue
            section = _SECTION.match(stripped)
            if section and "....." not in stripped:
                self._begin_section(section, cleaned, index, viewer)
                index = self._cursor
                continue
            marker = _accept_marker(line)
            if marker is not None and self._article is not None:
                self._begin_marker(marker[0], marker[1], stripped, viewer)
                index += 1
                continue
            if self._article is not None:
                if self._section_number is None and not self._buffer.lines:
                    self._section_number = ""
                    self._stack = []
                    self._open_buffer("Preamble")
                self._add(stripped, viewer)
            index += 1

    def close(self) -> None:
        self._flush()

    def chunks(self) -> list[Chunk]:
        counts: dict[str, int] = {}
        built: list[Chunk] = []
        for article, title, section, start, end, body in self._built:
            slug = _slug(section)
            number = counts.get(slug, 0)
            counts[slug] = number + 1
            article_bit = f"a{article}" if article is not None else "exhibit"
            printed_start = _printed(start, self._page_offset)
            printed_end = _printed(end, self._page_offset)
            if article is not None:
                heading = f"Article {article}. {title}".strip()
            else:
                heading = title or section
            text = f"{heading}\nSection {section}\n\n{body}".strip()
            built.append(
                Chunk(
                    id=f"{article_bit}-{slug}-{number}",
                    article_number=article,
                    article_title=title,
                    section=section,
                    page_start=printed_start,
                    page_end=printed_end,
                    text=text,
                    source_url=f"{self._source}#page={start}",
                )
            )
        return built

    def _begin_article(self, token: str, lines: list[str], index: int, viewer: int) -> None:
        self._flush()
        self._in_exhibit = False
        self._article = roman_to_int(token)
        titles: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            stripped = lines[cursor].strip()
            if not stripped:
                cursor += 1
                continue
            if stripped.isupper() and len(stripped) < 80 and not stripped.startswith("SECTION"):
                titles.append(stripped)
                cursor += 1
                continue
            break
        self._article_title = " ".join(titles)
        self._section_number = None
        self._stack = []
        self._buffer.clear()
        self._cursor = cursor

    def _begin_section(
        self,
        section: re.Match[str],
        lines: list[str],
        index: int,
        viewer: int,
    ) -> None:
        title = section.group(2).strip()
        if not title:
            self._add(section.group(0), viewer)
            self._cursor = index + 1
            return
        cursor = index + 1
        while cursor < len(lines) and title and not title.endswith("."):
            nxt = lines[cursor]
            stripped = nxt.strip()
            if not stripped:
                cursor += 1
                continue
            indented = len(nxt) - len(nxt.lstrip()) >= 8
            if indented and _accept_marker(nxt) is None and _SECTION.match(stripped) is None:
                title = f"{title} {stripped}".strip()
                cursor += 1
                continue
            break
        self._flush()
        self._section_number = section.group(1)
        self._stack = []
        heading = title.rstrip(".").strip()
        self._open_buffer(_label(self._section_number, [], heading))
        self._add(f"Section {self._section_number}. {title}", viewer)
        self._cursor = cursor

    def _begin_marker(self, token: str, rest: str, line: str, viewer: int) -> None:
        if self._section_number is None:
            self._section_number = ""
        definitions = self._article == 1 and self._section_number == "1"
        kind = _marker_kind(token, definitions=definitions, stack=self._stack)
        self._flush()
        self._stack = _apply_marker(self._stack, kind, token)
        base = self._section_number
        self._open_buffer(_label(base, self._stack, _short_heading(rest)))
        self._add(line, viewer)

    def _begin_exhibit(self, exhibit_id: str, line: str, viewer: int) -> None:
        self._in_exhibit = True
        self._article = None
        self._article_title = ""
        self._section_number = None
        self._stack = []
        self._open_buffer(f"Exhibit {exhibit_id}")
        self._buffer.article_title = f"Exhibit {exhibit_id}"
        self._add(line, viewer)

    def _open_buffer(self, section: str) -> None:
        self._buffer = _Buffer()
        self._buffer.article = self._article
        self._buffer.article_title = self._article_title
        self._buffer.section = section

    def _add(self, line: str, viewer: int) -> None:
        if not self._buffer.section and self._article is not None:
            self._open_buffer("Preamble")
        self._buffer.lines.append((viewer, line))

    def _flush(self) -> None:
        if not self._buffer.lines:
            self._buffer = _Buffer()
            return
        limit = 16000 if self._buffer.article is None else None
        groups = _page_groups(self._buffer.lines, limit=limit)
        section = self._buffer.section or "Preamble"
        for part, group in enumerate(groups, start=1):
            body = "\n".join(line for _, line in group).strip()
            if not body:
                continue
            label = section if part == 1 else f"{section} part {part}"
            self._built.append(
                (
                    self._buffer.article,
                    self._buffer.article_title,
                    label,
                    group[0][0],
                    group[-1][0],
                    body,
                )
            )
        self._buffer = _Buffer()


def _label(section_number: str, stack: list[tuple[str, str]], heading: str) -> str:
    path = section_number + "".join(f"({token})" for _, token in stack)
    if not path:
        path = "Preamble"
    if heading:
        return f"{path} {heading}".strip()
    return path


def _page_groups(
    lines: list[tuple[int, str]],
    *,
    limit: int | None,
) -> list[list[tuple[int, str]]]:
    if limit is None:
        return [lines]
    groups: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_chars = 0
    for viewer, line in lines:
        extra = len(line) + 1
        if current and current_chars + extra > limit and viewer != current[-1][0]:
            groups.append(current)
            current = []
            current_chars = 0
        current.append((viewer, line))
        current_chars += extra
    if current:
        groups.append(current)
    return groups or [lines]


def _printed(viewer: int, page_offset: int) -> int:
    printed = viewer - page_offset
    if printed < 1:
        return viewer
    return printed

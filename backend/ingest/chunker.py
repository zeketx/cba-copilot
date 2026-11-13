
from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain import Chunk

_ARTICLE_RE = re.compile(
    r"^#\s+Article\s+([0-9]+|[IVXLCDM]+)\b\.?\s*(.*?)\s*$",
    re.IGNORECASE,
)
_EXHIBIT_RE = re.compile(
    r"^#\s+Exhibit\s+([A-Z][A-Z0-9-]*)\b\.?\s*(.*?)\s*$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^##\s+(?:Section\s+)?(.+?)\s*$", re.IGNORECASE)
_PAGE_RE = re.compile(r"^<!--\s*pdf-page:\s*(\d+)(?:\s+printed:\s+(\S+))?\s*-->\s*$")
_SUBSECTION_HEADING = re.compile(r"^###\s+.+")
_AID_NAME_RE = re.compile(r"^(\d+)-")

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

DEFAULT_MAX_SECTION_CHARS = 6000

def article_number_from_aid_name(filename: str) -> int | None:

    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    match = _AID_NAME_RE.match(name)
    if match is None:
        return None
    return int(match.group(1))

def roman_to_int(value: str) -> int:
    total = 0
    previous = 0
    for char in reversed(value.upper()):
        number = _ROMAN[char]
        if number < previous:
            total -= number
        else:
            total += number
            previous = number
    return total

def _article_number(token: str) -> int:
    if token.isdigit():
        return int(token)
    return roman_to_int(token)

def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "section"

@dataclass
class _Line:
    page: int | None
    text: str

@dataclass
class _Section:
    article_number: int | None
    article_title: str
    section: str
    lines: list[_Line]

def _header(section: _Section, section_label: str) -> str:
    if section.article_number is None:
        heading = section.article_title or section_label or "Exhibit"
        if section_label and section_label != heading:
            return f"{heading}\n{section_label}\n\n"
        return f"{heading}\n\n"
    article = f"Article {section.article_number}. {section.article_title}".strip()
    return f"{article}\nSection {section_label}\n\n"

def _page_span(lines: list[_Line]) -> tuple[int | None, int | None]:
    pages = [line.page for line in lines if line.page is not None and line.text.strip()]
    if not pages:
        pages = [line.page for line in lines if line.page is not None]
    if not pages:
        return None, None
    return pages[0], pages[-1]

def _anchored(source_url: str, page: int | None) -> str:
    if page is None:
        return source_url.split("#", 1)[0]
    base = source_url.split("#", 1)[0]
    return f"{base}#page={page}"

def _has_body(lines: list[_Line]) -> bool:
    return any(line.text.strip() and not line.text.strip().startswith("#") for line in lines)

# Known words the PDF extractor split with a space. Real two-word phrases are not listed.
_PDF_WORD_SPLITS: tuple[tuple[str, str], ...] = (
    ("V eteran", "Veteran"),
    ("Agen t", "Agent"),
    ("F ree", "Free"),
    ("O peration", "Operation"),
    ("Ro om", "Room"),
    ("acquir ed", "acquired"),
    ("assi gnment", "assignment"),
    ("Ot her", "Other"),
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
_LEADING_MARKER = re.compile(r"^\(([a-z]+|\d+)\)\s+")
_LEADING_MARKER_RUN = re.compile(r"^((?:\([^)]+\))(?:\s+\([^)]+\))*)")


def rejoin_pdf_word_splits(value: str) -> str:
    for broken, fixed in _PDF_WORD_SPLITS:
        value = value.replace(broken, fixed)
    return value


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
    if len(token) == 1 and len(last_letter) == 1 and ord(token) == ord(last_letter) + 1:
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


def _leading_tokens(stripped: str) -> list[str]:
    tokens: list[str] = []
    rest = stripped
    while True:
        match = _LEADING_MARKER.match(rest)
        if match is None:
            break
        token = match.group(1)
        if not token.isdigit() and len(token) > 6:
            break
        tokens.append(token)
        rest = rest[match.end() :]
    return tokens


def _compact_leading_markers(value: str) -> str:
    match = _LEADING_MARKER_RUN.match(value)
    if match is None:
        return value
    run = match.group(1)
    return run.replace(" ", "") + value[len(run) :]


def _is_subsection_cut(stripped: str) -> bool:
    if _SUBSECTION_HEADING.match(stripped):
        return True
    tokens = _leading_tokens(stripped)
    if not tokens:
        return False
    rest = stripped
    for _token in tokens:
        match = _LEADING_MARKER.match(rest)
        if match is None:
            return False
        rest = rest[match.end() :]
    if not rest:
        return False
    first = tokens[0]
    if first.isdigit() or first in _ROMAN_MARKERS:
        return True
    return len(first) == 1 and first.isalpha()


def _parent_prefix(stack: list[tuple[str, str]], token: str, *, definitions: bool) -> str:
    kind = _marker_kind(token, definitions=definitions, stack=stack)
    if kind == "letter":
        kept: list[tuple[str, str]] = []
    elif kind == "number":
        kept = [item for item in stack if item[0] == "letter"]
    else:
        kept = [item for item in stack if item[0] in {"letter", "number"}]
    return "".join(f"({item})" for _, item in kept)


def _marker_prefixes(section: _Section) -> list[str]:
    definitions = _is_definition_section(section)
    stack: list[tuple[str, str]] = []
    prefixes: list[str] = []
    for line in section.lines:
        tokens = _leading_tokens(line.text.strip())
        if not tokens:
            prefixes.append("")
            continue
        prefixes.append(_parent_prefix(stack, tokens[0], definitions=definitions))
        for token in tokens:
            kind = _marker_kind(token, definitions=definitions, stack=stack)
            stack = _apply_marker(stack, kind, token)
    return prefixes


def _stored_section(name: str, prefix: str, heading: str) -> str:
    heading = _compact_leading_markers(heading)
    if not heading:
        return rejoin_pdf_word_splits(name)
    if prefix:
        if heading.startswith("("):
            combined = f"{prefix}{heading}"
        else:
            combined = f"{prefix} {heading}".strip()
        stored = f"{name} / {combined}"
    else:
        stored = f"{name} / {heading}"
    return rejoin_pdf_word_splits(stored)

_DEFINITION_LINE = re.compile(r"^\(([a-z]+)\)\s+(\S.*)$")
_SUBPARAGRAPH = re.compile(r"^\((?:\d+|[ivxlcdm]+|[A-Z])\)\s+\S")
_SENTENCE_END = re.compile(r"""[.?!]["”’']?\s*$""")
_OPEN_QUOTES = "\"“‘'"


def _is_definition_section(section: _Section) -> bool:
    if section.article_number != 1:
        return False
    return re.match(r"^1(?:\.|\s|$)", section.section.strip()) is not None


def _definition_token(stripped: str) -> str | None:
    match = _DEFINITION_LINE.match(stripped)
    if match is None:
        return None
    token = match.group(1)
    if re.fullmatch(r"([a-z])\1*", token) is None:
        return None
    return token


def _next_definition(token: str) -> str:
    letter = token[0]
    if letter == "z":
        return "a" * (len(token) + 1)
    return chr(ord(letter) + 1) * len(token)


def _starts_definition(stripped: str, expected: str) -> bool:
    token = _definition_token(stripped)
    if token is None:
        return False
    rest = stripped.split(")", 1)[1].lstrip()
    # A quoted term is the defined word. An unquoted (i) or (1) stays in the parent.
    if rest[:1] in _OPEN_QUOTES:
        return True
    return token == expected


def _chars(lines: list[_Line]) -> int:
    return len("\n".join(line.text for line in lines).strip())


def _last_text(lines: list[_Line]) -> str:
    for line in reversed(lines):
        stripped = line.text.strip()
        if stripped:
            return stripped
    return ""


def _can_cut_before(current: list[_Line], line: _Line) -> bool:
    stripped = line.text.strip()
    if not stripped:
        return False
    if _SUBPARAGRAPH.match(stripped):
        return True
    return _SENTENCE_END.search(_last_text(current)) is not None


def _split_long_definition(lines: list[_Line], max_chars: int) -> list[list[_Line]]:
    if _chars(lines) <= max_chars:
        return [lines]
    pieces: list[list[_Line]] = []
    current: list[_Line] = []
    for line in lines:
        over = current and _chars(current) + len(line.text) + 1 > max_chars
        if over and _can_cut_before(current, line):
            pieces.append(current)
            current = []
        current.append(line)
    if current:
        pieces.append(current)
    return pieces or [lines]


def _split_definitions(
    section: _Section, max_section_chars: int
) -> list[tuple[str, str, list[_Line]]]:
    expected = "a"
    cuts: list[int] = []
    for index, line in enumerate(section.lines):
        stripped = line.text.strip()
        if not _starts_definition(stripped, expected):
            continue
        token = _definition_token(stripped)
        if token is None:
            continue
        cuts.append(index)
        expected = _next_definition(token)
    if not cuts:
        return []
    prefixes = _marker_prefixes(section)
    groups: list[tuple[str, str, list[_Line]]] = []
    plain = section.section
    if cuts[0] > 0 and _has_body(section.lines[: cuts[0]]):
        groups.append((plain, rejoin_pdf_word_splits(plain), section.lines[: cuts[0]]))
    for position, start in enumerate(cuts):
        end = cuts[position + 1] if position + 1 < len(cuts) else len(section.lines)
        heading = section.lines[start].text.strip()
        text_label = f"{section.section} / {heading}"
        stored = _stored_section(section.section, prefixes[start], heading)
        pieces = _split_long_definition(section.lines[start:end], max_section_chars)
        for part, piece in enumerate(pieces, start=1):
            label = text_label if part == 1 else f"{text_label} part {part}"
            section_label = stored if part == 1 else f"{stored} part {part}"
            if _has_body(piece):
                groups.append((label, section_label, piece))
    return groups


def _split_groups(
    section: _Section, max_section_chars: int
) -> list[tuple[str, str, list[_Line]]]:
    if _is_definition_section(section):
        defined = _split_definitions(section, max_section_chars)
        if defined:
            return defined
    plain = section.section
    stored_plain = rejoin_pdf_word_splits(plain)
    body = "\n".join(line.text for line in section.lines).strip()
    if len(body) <= max_section_chars:
        return [(plain, stored_plain, section.lines)]

    cuts = [
        index
        for index, line in enumerate(section.lines)
        if _is_subsection_cut(line.text.strip())
    ]
    if not cuts:
        return [(plain, stored_plain, section.lines)]

    prefixes = _marker_prefixes(section)
    groups: list[tuple[str, str, list[_Line]]] = []
    if cuts[0] > 0 and _has_body(section.lines[: cuts[0]]):
        groups.append((plain, stored_plain, section.lines[: cuts[0]]))
    for position, start in enumerate(cuts):
        end = cuts[position + 1] if position + 1 < len(cuts) else len(section.lines)
        heading = re.sub(r"^#+\s*", "", section.lines[start].text.strip()).strip()
        text_label = f"{section.section} / {heading}"
        section_label = _stored_section(section.section, prefixes[start], heading)
        group_lines = section.lines[start:end]
        if _has_body(group_lines):
            groups.append((text_label, section_label, group_lines))
    return groups or [(plain, stored_plain, section.lines)]

def chunk_markdown(
    text: str,
    *,
    source_url: str,
    article_number: int | None = None,
    article_title: str | None = None,
    max_section_chars: int = DEFAULT_MAX_SECTION_CHARS,
    id_prefix: str = "",
) -> list[Chunk]:
    current_number = article_number
    current_title = article_title or ""
    current_page: int | None = None
    sections: list[_Section] = []
    current: _Section | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        if any(line.text.strip() for line in current.lines):
            sections.append(current)
        current = None

    for raw in text.splitlines():
        page_match = _PAGE_RE.match(raw.strip())
        if page_match:
            current_page = int(page_match.group(1))
            continue

        article_match = _ARTICLE_RE.match(raw.strip())
        if article_match:
            flush()
            current_number = _article_number(article_match.group(1))
            current_title = article_match.group(2).strip() or current_title
            continue

        exhibit_match = _EXHIBIT_RE.match(raw.strip())
        if exhibit_match:
            flush()
            current_number = None
            exhibit_id = exhibit_match.group(1).upper()
            exhibit_title = exhibit_match.group(2).strip()
            current_title = (
                f"Exhibit {exhibit_id}. {exhibit_title}"
                if exhibit_title
                else f"Exhibit {exhibit_id}"
            )
            continue

        section_match = _SECTION_RE.match(raw.strip())
        if section_match:
            flush()
            heading = section_match.group(1).strip()
            if current_number is None and current_title.startswith("Exhibit "):
                exhibit_id = current_title.split(".", 1)[0]
                section_name = (
                    heading
                    if heading.startswith(exhibit_id)
                    else f"{exhibit_id} / {heading}"
                )
            else:
                section_name = heading
            current = _Section(
                article_number=current_number,
                article_title=current_title,
                section=section_name,
                lines=[],
            )
            continue

        if current is None:
            if not raw.strip():
                continue
            current = _Section(
                article_number=current_number,
                article_title=current_title,
                section=current_title or "Preamble",
                lines=[],
            )
        current.lines.append(_Line(page=current_page, text=raw))

    flush()

    chunks: list[Chunk] = []
    for section in sections:
        grouped = _split_groups(section, max_section_chars)
        for index, (text_label, section_label, lines) in enumerate(grouped):
            body = "\n".join(line.text for line in lines).strip()
            page_start, page_end = _page_span(lines)
            number = section.article_number
            if number is not None:
                number_bit = f"a{number}"
            elif section.article_title.startswith("Exhibit "):
                number_bit = _slug(section.article_title.split(".", 1)[0])
            else:
                number_bit = "exhibit"
            chunks.append(
                Chunk(
                    id=f"{id_prefix}{number_bit}-{_slug(text_label)}-{index}",
                    article_number=number,
                    article_title=section.article_title,
                    section=section_label,
                    page_start=page_start,
                    page_end=page_end,
                    text=(_header(section, text_label) + body).strip(),
                    source_url=_anchored(source_url, page_start),
                )
            )
    return chunks

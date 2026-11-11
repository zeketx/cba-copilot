from __future__ import annotations

import re

from ingest.rows import references

_SLASH = re.compile(r"^(?P<num>\d+)\.\s+.+?\s+/\s+(?P<rest>.+)$", re.DOTALL)
_MARKERS = re.compile(r"^(?P<markers>(?:\([A-Za-z0-9]+\)\s*)+)")
_PATH = re.compile(r"^(?P<path>\d+(?:\([A-Za-z0-9]+\))*)")


def section_path(label: str) -> str | None:
    text = label.strip()
    slash = _SLASH.match(text)
    if slash:
        rest = slash.group("rest").strip()
        markers = _MARKERS.match(rest)
        if markers:
            compact = re.sub(r"\s+", "", markers.group("markers"))
            return f"{slash.group('num')}{compact}"
        plain = _PATH.match(rest)
        if plain:
            return plain.group("path")
        return slash.group("num")
    plain = _PATH.match(text)
    if plain:
        return plain.group("path")
    return None


def select_section_ids(rows: list[tuple[str, str]], ref_section: str) -> list[str]:
    target = section_path(ref_section)
    if target is None:
        return []
    exact: list[str] = []
    children: list[str] = []
    prefix = target + "("
    for passage_id, label in rows:
        path = section_path(label)
        if path == target:
            exact.append(passage_id)
        elif path is not None and path.startswith(prefix):
            children.append(passage_id)
    return exact or children


def citation_targets(text: str, article_number: int | None, section: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for item in references(text, article_number, section):
        article = item.get("article")
        ref_section = item.get("section")
        if isinstance(article, int) and isinstance(ref_section, str) and ref_section:
            found.append((article, ref_section))
    return found


from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "and",
        "or",
        "vs",
        "what",
        "how",
        "which",
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "can",
        "cant",
        "cannot",
        "not",
        "with",
        "above",
        "during",
        "may",
        "many",
        "who",
        "whom",
        "this",
        "that",
        "than",
        "into",
        "from",
        "by",
        "at",
        "as",
        "be",
        "it",
        "its",
        "their",
        "his",
        "her",
        "them",
        "about",
        "dont",
        "doesnt",
    }
)

def tokens(text: str) -> set[str]:
    found = {match.group(0) for match in _TOKEN_RE.finditer(text.lower())}
    return {token for token in found if len(token) > 2 and token not in STOPWORDS}

from __future__ import annotations

import re

ALIASES: tuple[tuple[str, str], ...] = (
    ("early bird", "early qualifying veteran free agent"),
    ("non-bird", "non-qualifying veteran free agent"),
    ("non bird", "non-qualifying veteran free agent"),
    ("second apron", "second apron level"),
    ("second-apron", "second apron level"),
    ("taxpayer mid-level", "taxpayer mid-level salary exception"),
    ("taxpayer mle", "taxpayer mid-level salary exception"),
    ("non-taxpayer", "non-taxpayer mid-level salary exception"),
    ("room mid-level", "mid-level salary exception for room teams"),
    ("bi-annual", "bi-annual exception"),
    ("65-game", "sixty-five regular season games league honors"),
    ("65 game", "sixty-five regular season games league honors"),
    ("sign-and-trade", "signed and traded section 8"),
    ("sign and trade", "signed and traded section 8"),
    ("two-way", "two-way contract"),
    ("bird", "qualifying veteran free agent"),
    ("awards", "league honors most valuable player defensive"),
    ("award", "league honors most valuable player defensive"),
    ("cap", "salary cap team salary"),
)


def expand_query(question: str) -> str:
    lowered = question.lower()
    extras: list[str] = []
    for phrase, expansion in ALIASES:
        pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
        if re.search(pattern, lowered):
            extras.append(expansion)
    if not extras:
        return question
    return f"{question} {' '.join(extras)}"

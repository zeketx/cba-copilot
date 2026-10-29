
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "corpus.json"

@lru_cache
def load_corpus() -> dict[str, object]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

def pdf_url() -> str:
    return str(load_corpus()["pdf_url"])

def printed_page_to_pdf_page(printed_page: int) -> int:

    offset = int(load_corpus()["pdf_page_offset"])
    return printed_page + offset

def source_url_for_printed_page(printed_page: int) -> str:
    return f"{pdf_url()}#page={printed_page_to_pdf_page(printed_page)}"

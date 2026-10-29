
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.corpus import source_url_for_printed_page
from app.domain import Chunk
from app.retrieval.embed import HashEmbedder
from app.retrieval.store import MemoryChunkStore

PASSAGES_PATH = Path(__file__).resolve().parents[1] / "evals" / "passages.yaml"

@lru_cache
def load_demo_chunks() -> tuple[Chunk, ...]:
    raw = yaml.safe_load(PASSAGES_PATH.read_text(encoding="utf-8"))
    chunks: list[Chunk] = []
    for item in raw:
        page = int(item["page_start"])
        chunks.append(
            Chunk(
                id=str(item["id"]),
                article_number=int(item["article_number"]),
                article_title=str(item["article_title"]),
                section=str(item["section"]),
                page_start=page,
                page_end=int(item["page_end"]),
                text=str(item["text"]).strip(),
                source_url=source_url_for_printed_page(page),
            )
        )
    return tuple(chunks)

def demo_embedder(dimensions: int = 1536) -> HashEmbedder:
    return HashEmbedder(dimensions=dimensions)

def demo_store(dimensions: int = 1536) -> MemoryChunkStore:
    embedder = demo_embedder(dimensions)
    chunks = list(load_demo_chunks())
    vectors = {
        chunk.id: embedder.embed_query(f"{chunk.section} {chunk.article_title} {chunk.text}")
        for chunk in chunks
    }
    return MemoryChunkStore(chunks, vectors)

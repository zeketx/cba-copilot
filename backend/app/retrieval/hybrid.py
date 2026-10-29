
from __future__ import annotations

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.embed import Embedder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.store import ChunkStore
from app.retrieval.text import tokens


def hybrid_retrieve(
    store: ChunkStore,
    question: str,
    embedder: Embedder,
    *,
    candidate_k: int = 50,
    top_k: int = 8,
    rrf_k: int = 60,
) -> list[Chunk]:
    expanded = expand_query(question)
    vector_ids = store.vector_search(embedder.embed_query(expanded), candidate_k)
    keyword_ids = store.keyword_search(expanded, candidate_k)
    fused = reciprocal_rank_fusion([vector_ids, keyword_ids], k=rrf_k)
    passages: list[Chunk] = []
    for passage_id, _score in fused[:top_k]:
        chunk = store.get(passage_id)
        if chunk is not None:
            passages.append(chunk)
    return passages

def evidence_is_adequate(question: str, passages: list[Chunk], *, minimum_overlap: int = 2) -> bool:

    if not passages:
        return False
    query_tokens = tokens(expand_query(question))
    if len(query_tokens) < minimum_overlap:
        return False
    best = 0
    for passage in passages[:3]:
        haystack = tokens(f"{passage.text} {passage.section} {passage.article_title}")
        best = max(best, len(query_tokens & haystack))
    return best >= minimum_overlap

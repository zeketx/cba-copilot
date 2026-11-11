from __future__ import annotations

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.embed import Embedder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.refs import citation_targets
from app.retrieval.store import ChunkStore
from app.retrieval.text import tokens
from app.retrieval.types import Retrieval


def hybrid_retrieve(
    store: ChunkStore,
    question: str,
    embedder: Embedder,
    *,
    candidate_k: int = 50,
    top_k: int = 8,
    rrf_k: int = 60,
    context_per_hit: int = 4,
    context_max: int = 16,
) -> Retrieval:
    if context_per_hit < 0 or context_max < 0:
        raise ValueError("context caps must be zero or greater")
    expanded = expand_query(question)
    vector_ids = store.vector_search(embedder.embed_query(expanded), candidate_k)
    keyword_ids = store.keyword_search(expanded, candidate_k)
    fused = reciprocal_rank_fusion([vector_ids, keyword_ids], k=rrf_k)
    hits: list[Chunk] = []
    for passage_id, _score in fused[:top_k]:
        chunk = store.get(passage_id)
        if chunk is not None:
            hits.append(chunk)
    context = _context_chunks(
        store,
        hits,
        per_hit=context_per_hit,
        total=context_max,
    )
    passage_ids = [chunk.id for chunk in hits]
    passage_ids.extend(chunk.id for chunk in context)
    return Retrieval(
        hits=hits,
        context=context,
        documents=store.source_documents(passage_ids),
    )

def _context_chunks(
    store: ChunkStore,
    hits: list[Chunk],
    *,
    per_hit: int,
    total: int,
) -> list[Chunk]:
    if per_hit == 0 or total == 0 or not hits:
        return []
    seen = {hit.id for hit in hits}
    context: list[Chunk] = []
    for hit in hits:
        if len(context) >= total:
            break
        added = 0
        for candidate in _candidates(store, hit):
            if candidate.id in seen:
                continue
            if added >= per_hit or len(context) >= total:
                break
            seen.add(candidate.id)
            context.append(candidate)
            added += 1
    return context

def _candidates(store: ChunkStore, hit: Chunk) -> list[Chunk]:
    found: list[Chunk] = []
    prev_id, next_id = store.neighbor_ids(hit.id)
    for passage_id in (prev_id, next_id):
        if passage_id is None:
            continue
        neighbor = store.get(passage_id)
        if neighbor is not None:
            found.append(neighbor)
    for article, section in citation_targets(hit.text, hit.article_number, hit.section):
        for passage_id in store.section_ids(article, section):
            target = store.get(passage_id)
            if target is not None:
                found.append(target)
    return found

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

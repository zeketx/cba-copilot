from __future__ import annotations

import time

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.embed import Embedder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.phrases import phrase_ranks
from app.retrieval.refs import citation_targets, select_section_ids
from app.retrieval.store import ChunkStore, documents_for
from app.retrieval.text import tokens
from app.retrieval.types import LoadedContext, Retrieval


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def _ordered_chunks(store: ChunkStore, passage_ids: list[str]) -> list[Chunk]:
    found = store.get_many(passage_ids)
    return [found[passage_id] for passage_id in passage_ids if passage_id in found]


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
    started = time.perf_counter()
    query_vec = embedder.embed_query(expanded)
    embed_ms = _elapsed_ms(started)
    started = time.perf_counter()
    vector_ids = store.vector_search(query_vec, candidate_k)
    vector_ms = _elapsed_ms(started)
    started = time.perf_counter()
    keyword_ids = store.keyword_search(expanded, candidate_k)
    keyword_ms = _elapsed_ms(started)
    seen: set[str] = set()
    candidate_ids: list[str] = []
    for passage_id in [*vector_ids, *keyword_ids]:
        if passage_id in seen:
            continue
        seen.add(passage_id)
        candidate_ids.append(passage_id)
    started = time.perf_counter()
    candidates = _ordered_chunks(store, candidate_ids)
    fetch_ms = _elapsed_ms(started)
    # Keyword overlap gathers candidates. It is too coarse to rank: "salary" hits
    # most of Article VII. Phrase matches are the lexical ranking, with keyword
    # overlap as a fallback when the question has no usable phrase.
    started = time.perf_counter()
    lexical_ids = phrase_ranks(question, candidates) or keyword_ids
    phrase_ms = _elapsed_ms(started)
    started = time.perf_counter()
    fused = reciprocal_rank_fusion(
        [vector_ids, lexical_ids],
        k=rrf_k,
        weights=[1.0, 2.0],
    )
    hit_ids = [passage_id for passage_id, _score in fused[:top_k]]
    hits = _ordered_chunks(store, hit_ids)
    fusion_ms = _elapsed_ms(started)
    articles = _cited_articles(hits)
    started = time.perf_counter()
    loaded = store.load_context(hits, articles)
    context = _context_chunks(
        hits,
        loaded,
        per_hit=context_per_hit,
        total=context_max,
    )
    context_ms = _elapsed_ms(started)
    db_ms = vector_ms + keyword_ms + fetch_ms + context_ms
    total_ms = embed_ms + db_ms + phrase_ms + fusion_ms
    return Retrieval(
        hits=hits,
        context=context,
        documents=documents_for(loaded.documents, [*hits, *context]),
        timings={
            "embed_ms": embed_ms,
            "db_ms": db_ms,
            "phrase_ms": phrase_ms,
            "fusion_ms": fusion_ms,
            "vector_ms": vector_ms,
            "keyword_ms": keyword_ms,
            "fetch_ms": fetch_ms,
            "context_ms": context_ms,
            "total_ms": total_ms,
            "retrieval_excluding_embed_ms": total_ms - embed_ms,
        },
    )

def _cited_articles(hits: list[Chunk]) -> list[int]:
    articles: list[int] = []
    seen: set[int] = set()
    for hit in hits:
        for article, _section in citation_targets(hit.text, hit.article_number, hit.section):
            if article in seen:
                continue
            seen.add(article)
            articles.append(article)
    return articles

def _context_chunks(
    hits: list[Chunk],
    loaded: LoadedContext,
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
        for candidate in _candidates(hit, loaded):
            if candidate.id in seen:
                continue
            if added >= per_hit or len(context) >= total:
                break
            seen.add(candidate.id)
            context.append(candidate)
            added += 1
    return context

def _candidates(hit: Chunk, loaded: LoadedContext) -> list[Chunk]:
    found: list[Chunk] = []
    prev, nxt = loaded.neighbors.get(hit.id, (None, None))
    for neighbor in (prev, nxt):
        if neighbor is not None:
            found.append(neighbor)
    for article, section in citation_targets(hit.text, hit.article_number, hit.section):
        chunks = loaded.articles.get(article, [])
        wanted = set(select_section_ids([(chunk.id, chunk.section) for chunk in chunks], section))
        for chunk in chunks:
            if chunk.id in wanted:
                found.append(chunk)
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

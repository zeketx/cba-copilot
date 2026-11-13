from __future__ import annotations

from app.domain import Chunk
from app.retrieval.aliases import expand_query
from app.retrieval.embed import Embedder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.phrases import phrase_ranks
from app.retrieval.refs import citation_targets, select_section_ids
from app.retrieval.store import ChunkStore, documents_for
from app.retrieval.text import tokens
from app.retrieval.types import LoadedContext, Retrieval


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
    seen: set[str] = set()
    candidates: list[Chunk] = []
    for passage_id in [*vector_ids, *keyword_ids]:
        if passage_id in seen:
            continue
        seen.add(passage_id)
        chunk = store.get(passage_id)
        if chunk is not None:
            candidates.append(chunk)
    lexical_ids = phrase_ranks(question, candidates)
    fused = reciprocal_rank_fusion([vector_ids, keyword_ids, lexical_ids], k=rrf_k)
    hits: list[Chunk] = []
    for passage_id, _score in fused[:top_k]:
        chunk = store.get(passage_id)
        if chunk is not None:
            hits.append(chunk)
    articles = _cited_articles(hits)
    loaded = store.load_context(hits, articles)
    context = _context_chunks(
        hits,
        loaded,
        per_hit=context_per_hit,
        total=context_max,
    )
    return Retrieval(
        hits=hits,
        context=context,
        documents=documents_for(loaded.documents, [*hits, *context]),
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

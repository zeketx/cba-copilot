
from __future__ import annotations

VECTOR_SEARCH_SQL = """
SELECT c.id,
       1 - (c.embedding <=> CAST(:query_vec AS vector)) AS score
FROM cba_chunks c
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> CAST(:query_vec AS vector)
LIMIT :limit
""".strip()

KEYWORD_SEARCH_SQL = """
SELECT c.id,
       ts_rank_cd(c.search_vector, query) AS score
FROM cba_chunks c,
     plainto_tsquery('english', :query_text) query
WHERE c.search_vector @@ query
ORDER BY score DESC, c.id
LIMIT :limit
""".strip()

def vector_search_sql() -> str:
    return VECTOR_SEARCH_SQL

def keyword_search_sql() -> str:
    return KEYWORD_SEARCH_SQL

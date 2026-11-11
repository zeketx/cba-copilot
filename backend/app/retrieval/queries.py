
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

NEIGHBOR_SQL = """
SELECT 'prev' AS slot, CAST(p.id AS text) AS id
FROM cba_chunks c
JOIN cba_chunks p
  ON p.document_id = c.document_id
 AND p.article_number IS NOT DISTINCT FROM c.article_number
 AND p.chunk_index = (
      SELECT max(p2.chunk_index)
      FROM cba_chunks p2
      WHERE p2.document_id = c.document_id
        AND p2.article_number IS NOT DISTINCT FROM c.article_number
        AND p2.chunk_index < c.chunk_index
 )
WHERE CAST(c.id AS text) = :chunk_id
UNION ALL
SELECT 'next' AS slot, CAST(n.id AS text) AS id
FROM cba_chunks c
JOIN cba_chunks n
  ON n.document_id = c.document_id
 AND n.article_number IS NOT DISTINCT FROM c.article_number
 AND n.chunk_index = (
      SELECT min(n2.chunk_index)
      FROM cba_chunks n2
      WHERE n2.document_id = c.document_id
        AND n2.article_number IS NOT DISTINCT FROM c.article_number
        AND n2.chunk_index > c.chunk_index
 )
WHERE CAST(c.id AS text) = :chunk_id
""".strip()

SECTION_CANDIDATES_SQL = """
SELECT CAST(c.id AS text) AS id, c.section
FROM cba_chunks c
WHERE c.article_number = :article
ORDER BY c.chunk_index
""".strip()

CHUNK_BY_ID_SQL = """
SELECT CAST(c.id AS text) AS id,
       c.article_number,
       c.article_title,
       c.section,
       c.page_start,
       c.page_end,
       c.text,
       c.source_url
FROM cba_chunks c
WHERE CAST(c.id AS text) = :chunk_id
""".strip()

SOURCE_DOCUMENTS_SQL = """
SELECT DISTINCT
       CAST(d.id AS text) AS id,
       d.title,
       d.source_url,
       d.sha256,
       d.cover_date,
       d.printed_term,
       d.page_offset,
       d.effective_start,
       d.effective_through
FROM source_documents d
JOIN cba_chunks c ON c.document_id = d.id
WHERE CAST(c.id AS text) IN :chunk_ids
ORDER BY id
""".strip()

def vector_search_sql() -> str:
    return VECTOR_SEARCH_SQL

def keyword_search_sql() -> str:
    return KEYWORD_SEARCH_SQL

def neighbor_sql() -> str:
    return NEIGHBOR_SQL

def section_candidates_sql() -> str:
    return SECTION_CANDIDATES_SQL

def chunk_by_id_sql() -> str:
    return CHUNK_BY_ID_SQL

def source_documents_sql() -> str:
    return SOURCE_DOCUMENTS_SQL

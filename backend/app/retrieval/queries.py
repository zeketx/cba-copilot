
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

NEIGHBOR_BATCH_SQL = """
SELECT 'prev' AS slot,
       CAST(c.id AS text) AS hit_id,
       CAST(p.id AS text) AS id,
       p.article_number,
       p.article_title,
       p.section,
       p.page_start,
       p.page_end,
       p.text AS body,
       p.source_url
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
WHERE CAST(c.id AS text) = ANY(string_to_array(:hit_ids, ','))
UNION ALL
SELECT 'next' AS slot,
       CAST(c.id AS text) AS hit_id,
       CAST(n.id AS text) AS id,
       n.article_number,
       n.article_title,
       n.section,
       n.page_start,
       n.page_end,
       n.text AS body,
       n.source_url
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
WHERE CAST(c.id AS text) = ANY(string_to_array(:hit_ids, ','))
""".strip()

CONTEXT_BATCH_SQL = """
SELECT 'chunk' AS kind,
       c.chunk_index,
       CAST(c.id AS text) AS id,
       c.article_number,
       c.article_title,
       c.section,
       c.page_start,
       c.page_end,
       c.text AS body,
       c.source_url,
       CAST(NULL AS text) AS title,
       CAST(NULL AS text) AS sha256,
       CAST(NULL AS text) AS cover_date,
       CAST(NULL AS text) AS printed_term,
       CAST(NULL AS integer) AS page_offset,
       CAST(NULL AS text) AS effective_start,
       CAST(NULL AS text) AS effective_through
FROM cba_chunks c
WHERE c.article_number = ANY(
  CASE
    WHEN :articles = '' THEN CAST(ARRAY[] AS integer[])
    ELSE CAST(string_to_array(:articles, ',') AS integer[])
  END
)
UNION ALL
SELECT 'document' AS kind,
       CAST(NULL AS integer) AS chunk_index,
       CAST(d.id AS text) AS id,
       CAST(NULL AS integer) AS article_number,
       CAST(NULL AS text) AS article_title,
       CAST(NULL AS text) AS section,
       CAST(NULL AS integer) AS page_start,
       CAST(NULL AS integer) AS page_end,
       CAST(NULL AS text) AS body,
       d.source_url,
       d.title,
       d.sha256,
       d.cover_date,
       d.printed_term,
       d.page_offset,
       d.effective_start,
       d.effective_through
FROM source_documents d
WHERE d.id IN (
  SELECT c.document_id
  FROM cba_chunks c
  WHERE CAST(c.id AS text) = ANY(string_to_array(:hit_ids, ','))
     OR c.article_number = ANY(
       CASE
         WHEN :articles = '' THEN CAST(ARRAY[] AS integer[])
         ELSE CAST(string_to_array(:articles, ',') AS integer[])
       END
     )
)
ORDER BY kind, chunk_index, id
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

CHUNKS_BY_IDS_SQL = """
SELECT CAST(c.id AS text) AS id,
       c.article_number,
       c.article_title,
       c.section,
       c.page_start,
       c.page_end,
       c.text,
       c.source_url
FROM cba_chunks c
WHERE CAST(c.id AS text) = ANY(string_to_array(:chunk_ids, ','))
""".strip()

def vector_search_sql() -> str:
    return VECTOR_SEARCH_SQL

def keyword_search_sql() -> str:
    return KEYWORD_SEARCH_SQL

def neighbor_batch_sql() -> str:
    return NEIGHBOR_BATCH_SQL

def context_batch_sql() -> str:
    return CONTEXT_BATCH_SQL

def chunk_by_id_sql() -> str:
    return CHUNK_BY_ID_SQL


def chunks_by_ids_sql() -> str:
    return CHUNKS_BY_IDS_SQL

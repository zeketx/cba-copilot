# Architecture

CBA Copilot is a sibling of document-copilot. One agreement replaces the SEC corpus. The modules that stay are the ones a cited answer needs.

## Data

A chunk is one article section. If that section is long and it has subsection headings, the chunker splits on those headings and keeps each subsection whole. A page marker never starts a chunk. The second-apron trade rules stay in one chunk when they sit in one section.

Each chunk carries the article number, the article title, the section, the PDF page range, and a source url with a `#page=` anchor.

The response type is a cited answer or a refusal. A claim cannot exist without a passage id. A refusal cannot carry claims.

## Retrieval

Live search is two SQL statements. One orders by pgvector cosine distance. The other ranks a generated `tsvector` with `ts_rank_cd`. Reciprocal rank fusion adds `1 / (k + rank)` across the two lists. `k` defaults to 60.

The offline store runs the same fusion over an in-memory keyword overlap and a hash embedding. Nickname expansion maps "Bird" to "Qualifying Veteran Free Agent" and similar pairs, because the agreement rarely uses the nickname.

Evidence is adequate only when a retrieved passage shares at least two content tokens with the expanded question. Otherwise the turn refuses before the drafter runs.

## Generation and checks

The PydanticAI agent returns a `DraftAnswer`. The default demo drafter quotes overlapping passages instead of calling a model. Tests also drive the agent with PydanticAI's `TestModel`, which returns a fixed object and does not call an API.

`validate_draft` drops a claim when any of its passage ids is outside the retrieved set. If no claim remains, the reason is `citations_dropped`.

## What the skeleton does not do

It does not extract the 676-page PDF. It does not call OpenAI. It does not open a Supabase connection. `PostgresChunkStore` has the SQL ready for that connection. `OpenAIEmbedder.embed_query` and `refuse_live_model` raise before a client is built.

## Shape that lost

One function that retrieved, drafted, and validated in a single module would have hidden less. The split into ingest, retrieval, the agent, and grounding keeps each check unit-testable and matches document-copilot. The public surface is `answer_question`, `chunk_markdown`, and `reciprocal_rank_fusion`.

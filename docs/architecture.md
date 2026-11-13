# Architecture

CBA Copilot is a sibling of document-copilot. One agreement replaces the SEC corpus. The modules that stay are the ones a cited answer needs.

## Data

A chunk is one article section. If that section is long and it has subsection headings, the chunker splits on those headings and keeps each subsection whole. A page marker never starts a chunk. The second-apron trade rules stay in one chunk when they sit in one section.

Each chunk carries the article number, the article title, the section, the PDF page range, and a source url with a `#page=` anchor.

The response type is a cited answer, a refusal, or a clarification. A claim cannot exist without a passage id. A refusal cannot carry claims.

## Retrieval

Live search fuses two fixed SQL statements. One orders by pgvector cosine distance. The other ranks a generated `tsvector` with `ts_rank_cd`. Reciprocal rank fusion adds `1 / (k + rank)` across the two lists. `k` defaults to 60.

`hybrid_retrieve` keeps that fused ranking, then loads context for every hit in two more fixed statements. One statement reads the previous and next chunk in the same article for all of the hits. The other reads every cited article and the source documents. A cross-reference in the hit text is parsed with the ingest reference rules. A reference that names no stored section is skipped. `RETRIEVAL_CONTEXT_PER_HIT` defaults to 4 and `RETRIEVAL_CONTEXT_MAX` defaults to 16.

The offline store runs the same fusion over an in-memory keyword overlap and a hash embedding, and it resolves the same context from the fixture list. Nickname expansion maps "Bird" to "Qualifying Veteran Free Agent" and similar pairs, because the agreement rarely uses the nickname.

Evidence is adequate only when one of the fused hits shares at least two content tokens with the expanded question. Context does not satisfy that check. When no fused hit shares those tokens, the turn refuses before the drafter runs. Context passages are still retrieved, so a claim may cite a neighbor or a resolved section. The fused hits keep their rank.

## Generation and checks

The PydanticAI agent returns a `DraftAnswer` of `DraftClaim` rows. Each draft claim carries a `quote`, a verbatim span copied from a cited passage. The default demo drafter sets that quote to the overlapping passage text. Tests also drive the agent with PydanticAI's `TestModel`, which returns a fixed object and does not call an API.

`validate_draft` keeps a claim only when every passage id was retrieved and the whitespace-normalized quote is a substring of at least one cited passage. The kept `Claim` keeps the quote, and the saved turn stores it, so the phase 10 grader can check the quote against the passage while the claim text paraphrases it. The HTTP `PublicClaim` does not send the quote. The retrieved set is the fused hits plus their context passages. If no claim remains, the reason is `citations_dropped`. An `ambiguous` or `missing_inputs` draft becomes a clarification when the kept claims meet that status. A failed answer call is HTTP 502 `answer_failed` and does not persist the turn.

## What the skeleton does not do

The ask path does not extract the 676-page PDF and does not call OpenRouter. It does not open a Supabase connection. The fixture answers with `HashEmbedder`. `PostgresChunkStore` has the SQL ready for that connection. `OpenAIEmbedder.embed_query` raises before a client is built. `evals.prove --live` is the live answer path. It builds `AgentDrafter` after `require_live_settings`. The live embedder is `OpenRouterEmbedder` on `mongodb/voyage-4-lite` at 1024 dimensions. Ingest calls it only with `--live` and `OPENROUTER_API_KEY`. Chunk text uses `input_type` `document`. A query uses `input_type` `query`. Those are the values in Voyage's embeddings API. OpenRouter's `input_type` field is a string, and this model is forwarded to Voyage. The embedding bench uses the same client, and only after `--live`.

## Shape that lost

One function that retrieved, drafted, and validated in a single module would have hidden less. The split into ingest, retrieval, the agent, and grounding keeps each check unit-testable and matches document-copilot. The public surface is `answer_question`, `chunk_markdown`, and `reciprocal_rank_fusion`.

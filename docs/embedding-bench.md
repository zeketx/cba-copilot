# Compare embedders on the CBA

Run this when you want recall, cost, and latency for a candidate embedding model. The live index is `mongodb/voyage-4-lite` at 1024 dimensions. The re-index commands are in [Set up the backend](guides/backend-setup.md). The ask path stays on the hash embedder. This bench does not write the database.

## Run the bench

From `backend/`:

```bash
uv run python -m evals.embed_bench --models hash
```

That command needs the July 2023 PDF at `data/downloads/2023-nba-cba.pdf`. From the repo root, download it with `python data/download_cba.py`. The PDF stays gitignored. You also need `pdftotext` (Poppler).

The hash row is free and does not call the network. A later run reads `backend/evals/reports/cache/` and does not embed those chunks again. A Voyage cache file name ends in `--document`, because those vectors were embedded with `input_type` `document`. An older file named only from the model slug is left unread.

To score Qwen and Voyage, set `OPENROUTER_API_KEY` in the environment or in `backend/.env`, then run:

```bash
uv run python -m evals.embed_bench --live --models qwen/qwen3-embedding-8b,mongodb/voyage-4-lite
```

Add `mongodb/voyage-4` to `--models` when you want the third catalog price. The hash row is included either way.

Without `--live`, the command refuses and sends no request. With `--live` and no key, it exits before a request and names `OPENROUTER_API_KEY`.

Check that every draft question still matches a chunk, without embedding:

```bash
uv run python -m evals.embed_bench --models hash --check-questions
```

## Read the report

The command writes `backend/evals/reports/embed-bench.md` and `embed-bench.json`. Both stay gitignored.

Read the draft row first. Those questions are marked `draft: true` in `backend/evals/draft_questions.yaml` for review. The original six stay in `questions.yaml`. A question with no matching chunk label is listed as unscored and is left out of the average.

Dense recall is a full-corpus cosine ranking. Hybrid recall is the app's in-memory keyword list fused with the vector list by reciprocal rank fusion. `candidate_k` and `rrf_k` come from settings, same as the ask path. Keyword overlap here is the in-memory stand-in, not Postgres full text.

`any` scores 1 when one expected section is inside the cutoff. `all` scores the fraction of expected sections found. MRR uses the rank of the first matching section.

Index dollars are `usage.prompt_tokens` from OpenRouter, times the price per million tokens. The price comes from the models endpoint (`output_modalities=embeddings`). If that call fails, the report uses the pinned table and says `pinned`. A cache hit shows zero dollars in the this-run column. Hash is free and reports no provider tokens.

Query p50 and p95 time only `embed_query`, one pass. The percentile is nearest-rank with `ceil`. Float32 bytes are `chunks × dimensions × 4`. That is a storage estimate for a vector column. This bench does not write the database.

Do not treat the hash row as a semantic bake-off. It is a signed bag of tokens, so its recall follows lexical overlap after the app's nickname expansion.

## Score the live store

This path reads `cba_chunks` for one source document and ranks with `hybrid_retrieve` and `PostgresChunkStore`. It does not embed the corpus and it does not open the database unless you pass `--database`.

From `backend/`, with `DATABASE_URL`, `EMBEDDING_PROVIDER=openrouter`, `EMBEDDING_MODEL=mongodb/voyage-4-lite`, and `OPENROUTER_API_KEY` set in the environment or in `backend/.env`:

```bash
uv run python -m evals.embed_bench --database
```

Without `--database`, the command stays on the in-memory bench and does not connect. With `--database` and no `DATABASE_URL`, or with OpenRouter selected and no key, it exits with status 2 before a connection and before a request.

The report writes the same two files. Draft and all-question rows list hybrid recall@5, recall@8, and MRR. Query p95 times the whole `hybrid_retrieve` call, which is the query embedding plus both Postgres searches. A miss at recall@5 lists the top five stored section labels. A question whose label is absent from the corpus still counts in the average.

# Set up the backend

From `backend/`:

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run uvicorn app.main:app --reload
```

`GET /api/health` returns `{"ok":"true","mode":"fake"}`.

`POST /api/ask` with `{"question":"..."}` answers from the fixture corpus. No API key is required. A question and each chat message may be at most 4,000 characters. `POST /api/chat/stream` accepts at most 32 messages. A longer question, a longer message, or more messages returns 422 and does not answer.

Limits are in-memory and reset when the process restarts. `POST /api/ask` and `POST /api/chat/stream` share 10 calls per signed-in user per 60 seconds. The 11th call in that window is 429 `rate_limited` and does not retrieve or draft. `POST /api/access-requests` allows 5 calls per client address per 600 seconds (429 `rate_limited`) and 100 distinct emails in the process (429 `access_requests_full`, and that email is not stored). A repeat of an email this process already stored still returns 200. The client address is the first `X-Forwarded-For` hop when the header is present, otherwise the socket peer. Change the budgets with `ANSWER_RATE_LIMIT`, `ANSWER_RATE_WINDOW_SECONDS`, `ACCESS_REQUEST_RATE_LIMIT`, `ACCESS_REQUEST_RATE_WINDOW_SECONDS`, and `ACCESS_REQUEST_CAP`.

`uv run python -m evals.runner` runs the six questions on stand-in models. `--live` exits with status 2 and does not call a model.

Copy `backend/.env.example` to `backend/.env` only when you are ready to point Alembic at Supabase. The offline tests ignore a missing `.env`.

`uv run python -m ingest load --dry-run` reads the official PDF and prints page, offset, and chunk counts. It does not write to the database. `uv run python -m ingest load` upserts one `source_documents` row and the `cba_chunks` rows.

## Re-index the corpus

The live model is `mongodb/voyage-4-lite` through OpenRouter, at 1024 dimensions. Chunk text is embedded with `input_type` `document`. A query embedding uses the same model with `input_type` `query`. The fixture server keeps the hash embedder, so a key in `backend/.env` does not change an answer from `/api/ask`.

`uv run python -m ingest embed` exits with status 2. It does not open the database and it does not call OpenRouter.

To fill the index, set `OPENROUTER_API_KEY` in the environment or in `backend/.env`. From `backend/`:

```bash
uv run alembic upgrade head
uv run python -m ingest embed --live
```

`alembic upgrade head` changes `cba_chunks.embedding` from `vector(1536)` to `vector(1024)`, drops and recreates the HNSW index, and sets every stored vector to null. `ingest embed --live` then embeds each null chunk. A second run skips chunks that already have a vector.

With `--live` and no `OPENROUTER_API_KEY`, the command exits with status 2 and sends no request.

After the re-index, score the same model from `backend/`. Delete `backend/evals/reports/cache/` first if it still holds a Voyage file from before `input_type` was set.

```bash
uv run python -m evals.embed_bench --live --models mongodb/voyage-4-lite
```

Read `backend/evals/reports/embed-bench.md`. The in-memory gate is draft hybrid recall@5 of at least 0.93, and query p95 of at most 500 ms. That p95 times `embed_query` only. The in-memory bench does not query pgvector.

After `ingest load` has rewritten chunk text, score the live store. `ingest load` updates `cba_chunks` in place by `chunk_index`, so a longer Article I shifts later rows and clears their embeddings. `ingest embed --live` fills every null vector.

```bash
uv run python -m evals.embed_bench --database
```

That command needs the same `DATABASE_URL` and OpenRouter settings. It refuses without `--database`. The live gate from issue 11 is draft hybrid recall@5 of at least 0.90, Bird rights, Team Salary, and Minimum Team Salary inside the top 5, and query p95 of at most 500 ms. This p95 times `hybrid_retrieve`.

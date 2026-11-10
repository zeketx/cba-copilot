# Set up the backend

From `backend/`:

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run uvicorn app.main:app --reload
```

`GET /api/health` returns `{"ok":"true","mode":"fake"}`.

`POST /api/ask` with `{"question":"..."}` answers from the fixture corpus. No API key is required.

`uv run python -m evals.runner` runs the six questions on stand-in models. `--live` exits with status 2 and does not call a model.

Copy `backend/.env.example` to `backend/.env` only when you are ready to point Alembic at Supabase. The offline tests ignore a missing `.env`.

`uv run python -m ingest load --dry-run` reads the official PDF and prints page, offset, and chunk counts. It does not write to the database. `uv run python -m ingest load` upserts one `source_documents` row and the `cba_chunks` rows.

`uv run python -m ingest embed` fills embeddings for chunks that still have none.

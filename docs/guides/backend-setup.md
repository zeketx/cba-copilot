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

# How to prove the 2023 CBA corpus

From `backend/`, after ingest has loaded the official PDF and filled embeddings:

```bash
uv run python -m evals.prove --live
```

The command reads settings from the environment or `backend/.env`. It needs these names. It never prints their values.

- `DATABASE_URL`
- `SUPABASE_URL`
- The answer key for `ANSWER_PROVIDER`: `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`
- `ANSWER_MODEL` when `ANSWER_PROVIDER` is not `openai`
- The embedding key for `EMBEDDING_PROVIDER`: `OPENROUTER_API_KEY` or `OPENAI_API_KEY`

It writes `docs/phase10/runs/<UTC timestamp>/results.json` and `summary.md`. The process exits 0 only when every phase 10 case passes.

Without `--live` the same command uses the hash embedder, the overlap drafter, and the fixture passages. It writes a temp directory and prints that path. Failures there only mean the overlap drafter is not a live model.

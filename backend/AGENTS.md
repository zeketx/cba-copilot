# Backend

Read [../AGENTS.md](../AGENTS.md) first.

## Layout

```text
backend/
├── app/
│   ├── api.py            # HTTP shell
│   ├── config.py         # settings
│   ├── pipeline.py       # retrieve, draft, validate
│   ├── assistant/        # PydanticAI output and drafters
│   ├── retrieval/        # fusion, SQL, in-memory store
│   ├── grounding/        # citation drop
│   └── database/         # SQLAlchemy models
├── alembic/
├── ingest/chunker.py
├── evals/                # six-question harness
└── tests/
```

## Checks

```bash
uv run ruff check .
uv run pytest
uv run python -m evals.runner
```

`uv run python -m evals.embed_bench --models hash` scores the hash embedder when the gitignored CBA PDF is on disk. Add `--live` before any OpenRouter call. See `docs/embedding-bench.md`.

Tests must pass with no network, no database, and no API key.

`PostgresChunkStore` and `OpenRouterEmbedder` are the live edges. `OpenAIEmbedder.embed_query` still raises before a client is built. Do not call them from tests.

Alembic is the schema. Generated `search_vector` and the HNSW and GIN indexes live in the migration because autogenerate does not own them.

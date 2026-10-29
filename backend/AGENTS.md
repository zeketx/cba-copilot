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

Tests must pass with no network, no database, and no API key.

`PostgresChunkStore` and `OpenAIEmbedder` are the live edges. Do not call them from tests.

Alembic is the schema. Generated `search_vector` and the HNSW and GIN indexes live in the migration because autogenerate does not own them.

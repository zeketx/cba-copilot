# Agent instructions

Read this before editing the repo.

## Stack

- Backend: Python 3.12, FastAPI, PydanticAI, SQLAlchemy, Alembic
- Frontend: Vite, React, TypeScript, Tailwind, pnpm
- Database, when the owner creates it: a new Supabase project, pgvector, and Postgres full text
- Models, when live calls are enabled: `ANSWER_PROVIDER` is `openai`, `google`, or `openrouter`. The OpenAI chat default is `gpt-4o`. Live embeddings are `mongodb/voyage-4-lite` through OpenRouter at 1024 dimensions. Google uses `GEMINI_API_KEY`. OpenRouter uses `OPENROUTER_API_KEY`.

The offline default uses a hash embedder at 1024 dimensions and an overlap drafter. Do not call OpenAI, OpenRouter, or create a Supabase project from an agent session.

## Layout

```text
cba-copilot/
├── AGENTS.md
├── data/                 # download scripts, corpus.json, gitignored PDF
├── definitions/          # draft glossary
├── docs/
├── backend/
└── frontend/
```

## Rules

- One corpus, the 2023 CBA. Do not add SEC, XBRL, or financial-statement code.
- Do not ingest Larry Coon's FAQ. Do not scrape Hoops Rumors or RealGM.
- Do not vendor the GPL-3.0 markdown aid.
- Do not commit `.env` files or the PDF.
- Do not print secrets.
- Settings live in `backend/app/config.py`. Do not call `os.getenv` in app code.
- Chunk on article and section boundaries. Do not split a rule across arbitrary pages.
- A claim that cites a passage outside the retrieved set is dropped. If none remain, refuse.
- Keep the demo and the tests free of network calls.
- Every phase in `docs/TODO.md` opens with a one-line `**Story:**` in the form "As a ..., I want ..., so ...". Add one when you add a phase, and update it when the phase's goal changes.

## Dependencies

Add a library when the alternative is a real protocol or a hard parser. Do not add a helper for a few lines of stdlib. Say in the commit why a new dependency is there.

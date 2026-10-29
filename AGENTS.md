# Agent instructions

Read this before editing the repo.

## Stack

- Backend: Python 3.12, FastAPI, PydanticAI, SQLAlchemy, Alembic
- Frontend: Vite, React, TypeScript, Tailwind, pnpm
- Database, when the owner creates it: a new Supabase project, pgvector, and Postgres full text
- Models, when live calls are enabled: OpenAI `text-embedding-3-small` at 1536 dimensions, chat `gpt-5.5`, grounding `gpt-4.1-mini`

The offline default uses a hash embedder and an overlap drafter. Do not call OpenAI or create a Supabase project from an agent session.

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

## Dependencies

Add a library when the alternative is a real protocol or a hard parser. Do not add a helper for a few lines of stdlib. Say in the commit why a new dependency is there.

# CBA Copilot build checklist

Work top to bottom. A phase is done when its exit check passes.

The pilot is one official PDF of the 2023 NBA CBA. Record its URL, sha256, cover date, and printed term before a live answer is shown. Do not commit the PDF. Unofficial markdown, fan sites, and salary-cap explainers are not sources. A later agreement, side letter, or amendment stays in phase 12 until this PDF passes phase 10.

Checked boxes match `main`. The stack is in `AGENTS.md`. Corpus rules are in `docs/corpus.md`. The offline demo answers from a fixture and does not call a paid model.

## 0. Already in the repo

- [x] `README.md` describes cited, refusal-first Q&A over the 2023 NBA CBA
- [x] `LICENSE`
- [x] `.cursor/settings.json` enables pstack
- [x] `.cursor/rules/grok-only.mdc`
- [x] `AGENTS.md` names Python 3.12, FastAPI, PydanticAI, Vite, React, TypeScript, Tailwind, pnpm, Supabase pgvector, and `text-embedding-3-small` at 1536 dimensions
- [x] `docs/architecture.md` states the request path, the chunk record, and the trust rule
- [x] `docs/corpus.md` states the official PDF, the gitignored download, the optional markdown aid, and the sources that stay out
- [x] `docs/guides/supabase-setup.md`, `docs/guides/backend-setup.md`, and `docs/guides/frontend-setup.md`
- [x] `backend/pyproject.toml` and `frontend/package.json`
- [x] `backend/.env.example` and `frontend/.env.example` list the variables and contain no secrets
- [x] `data/download_cba.py` saves the official PDF under `data/downloads/`, and the PDF is gitignored

## 1. Accounts and local corpus

- [x] Create the Supabase project in `docs/guides/supabase-setup.md` and stop before any paid project. v1 has no email auth. The project is `nba-cba-copilot`, ref `wxfscyrhpqnbimjdqvyf`, region `us-east-2`. The public schema had no tables on 2026-11-08
- [ ] Copy credentials into `backend/.env`. The service role and `DATABASE_URL` stay backend-only. Use the direct session URL, not the transaction pooler. `SUPABASE_URL` and `SUPABASE_ANON_KEY` are in the gitignored `backend/.env`. Still missing `SUPABASE_SERVICE_ROLE_KEY` and the database password for `DATABASE_URL`
- [x] The download script records the URL, the sha256, the cover date, and the printed term in a gitignored manifest. `data/corpus.json` has the URL, the dates, and a printed-to-viewer offset of 24, and it has no hash
- [x] The unofficial markdown aid is not vendored. `data/download_markdown_aid.py` writes it only with `--i-accept-the-unofficial-aid`, and every chunk still needs the official PDF page

**Exit:** `backend/.env` is filled, and `data/downloads/` contains the official PDF plus a manifest with its hash. A second download does not commit the PDF.

## 2. Boot both services

Backend (`docs/guides/backend-setup.md`):

- [x] `app/config.py` is the only settings module. The offline demo starts with an empty env. Live mode raises when `DATABASE_URL` or `SUPABASE_URL` is missing. App code does not call `os.getenv`
- [x] `app/main.py` is the FastAPI app. CORS reads `ALLOWED_ORIGINS`. Health is `GET /api/health`
- [ ] `uv run uvicorn app.main:app --reload` returns 200 from `/api/health`

Frontend (`docs/guides/frontend-setup.md`):

- [x] Vite, React, TypeScript, Tailwind, and shadcn/ui. pnpm only. One screen, no router. The dev server proxies `/api` to `http://127.0.0.1:8000`
- [ ] `pnpm typecheck` and `pnpm lint` are recorded as passing

**Exit:** both processes run locally and the frontend can reach `/api/health`.

## 3. Schema

On `main`: `source_documents` and `cba_chunks`. Still open: `users`, `chat_threads`, `chat_messages`, `message_citations`.

- [x] SQLAlchemy models in `app/database/models.py`
- [x] `alembic/env.py` imports that metadata and reads `Settings().sqlalchemy_database_url`
- [x] First migration in `alembic/versions/c0a2023b0001_cba_schema.py` creates:
  - [x] `create extension if not exists vector`
  - [x] an embedding column at 1536 dimensions
  - [x] generated `tsvector` on chunk text
  - [x] HNSW index on the embedding
  - [x] GIN index on `search_vector`
- [ ] GIN index on JSON metadata
- [ ] Chat tables, and RLS once auth exists
- [ ] `uv run alembic upgrade head` against the hosted database
- [x] A chunk can store the article number, the article title, the section, the page range, the source URL, the order in the file, and the token count
- [ ] Store the printed page and the viewer page as separate fields, and store the character offsets of the quote

**Exit:** `\dt` shows the corpus tables and the chat tables, `vector` is installed, and a second `upgrade head` is a no-op.

## 4. Auth

v1 has no auth. These stay open.

- [ ] Email sign-up and sign-in in the SPA
- [ ] `app/auth/dependencies.py` verifies `Authorization: Bearer` and exposes `get_current_user`
- [ ] Reject a missing or invalid token with 401 before any retrieval or model call
- [ ] Create a `users` row for the signed-in user
- [ ] 403 when an authenticated user opens another user's thread

**Exit:** a signed-in request reaches a protected route. A request with no token gets 401.

## 5. Chat shell

The demo screen posts one question and renders the reply. It does not save threads.

- [x] The screen calls `POST /api/ask` with `{ question }` and renders each claim or a refusal
- [ ] `src/lib/http.ts` sets the base URL, the bearer token, and timeouts, and types `ApiError` with a network-versus-HTTP flag
- [ ] `src/lib/api.ts` lists threads, creates a thread, and loads messages
- [ ] Thread list and new chat. Only the current user's threads
- [ ] `POST /chat/stream` accepts `{ threadId, messages }` and streams the assistant reply
- [ ] After a successful run, persist the user message and the assistant message
- [ ] Reload shows the same thread history

**Exit:** sign in, send a message, watch it stream, refresh, and see it still there. A second user cannot open that thread.

## 6. Ingestion

- [ ] Parse the official PDF into text that keeps the source URL, the printed page, and the viewer page. Measure the offset from the file. Do not assume an offset
- [ ] Upsert one `source_documents` row with that text, the source URL, the hash, the cover date, and the printed term. A second run updates the same row
- [x] `chunk_markdown` in `ingest/chunker.py` chunks by article and section, keeps a section whole across a page, and does not start a chunk on a page marker. Tests are in `tests/test_chunker.py` and do not use the network
- [ ] When a chunk tells the reader to apply another section, store that target on the chunk
- [ ] Embed chunks with `text-embedding-3-small` at 1536 dimensions
- [ ] Upsert `cba_chunks`. `search_vector` is generated by the database. A second ingest does not add duplicate chunks

**Exit:** the official PDF is queryable as rows in `source_documents` and `cba_chunks`, with embeddings, both page numbers, and a populated `search_vector`. The PDF file is still gitignored.

## 7. Hybrid retrieval

- [x] `reciprocal_rank_fusion` uses `k=60` unless `RETRIEVAL_RRF_K` sets another value
- [x] `vector_search_sql` and `keyword_search_sql` are fixed statements. No model-written SQL
- [x] The offline store fuses a hash embedding and keyword overlap. `tests/test_fusion.py` and `tests/test_retrieval.py` do not call the network
- [ ] Embed the user query with the same model used for the stored chunks
- [ ] Run the vector search and the lexical search on `cba_chunks` after ingest
- [ ] Load the winning chunks, the previous and next section in the same article, a section targeted by a cross-reference, and the source-document metadata
- [ ] A live check returns the section you name, with its article, section, printed page, and viewer page

**Exit:** a fixture question returns the fixture passage. A question with no shared words returns no passages. Neither test calls a network. The live check names a real section from the ingested PDF.

## 8. Grounded agent

- [x] `validate_draft` keeps a claim only when every passage id was retrieved. If one valid claim remains, that claim stays. If none remain, the reason is `citations_dropped`
- [x] No claims, or `insufficient_evidence`, refuses with `no_evidence`
- [x] Tests in `tests/test_grounding.py` and `tests/test_agent.py` use stand-in models and do not call the network
- [ ] Add `ambiguous` and `missing_inputs`. Ask which season or effective date applies when more than one passage matches and the question names neither
- [ ] Persist the turn only after the validator accepts it
- [ ] Stream text deltas first, then citation parts. Map auth, missing thread, retrieval, and grounding failures to 401, 403, 404, 422, and 502

**Exit:** one question from `backend/evals/questions.yaml` returns a cited answer through the API, and an off-corpus question returns `no_evidence`. The cited quote is contained in the retrieved passage.

## 9. Analyst UI

- [x] The demo renders each claim and a chip with the article, the section, and the page
- [x] A click opens a source panel for that passage
- [ ] The panel opens the official PDF at the viewer page. It currently shows an HTML excerpt
- [ ] Empty thread state, streaming state, and friendly errors for auth, network, and answer failure. A shared 502 is not labeled as a grounding refusal
- [ ] Rename and delete a chat from the sidebar
- [ ] Render assistant answer Markdown. Citations and user bubbles stay plain text
- [ ] Browser pass: sign in, ask, read a citation, open an old thread, rename, delete, sign out

**Exit:** a person can verify a claim from the citation without leaving the page, on the official PDF.

## 10. Prove the corpus

`backend/evals/questions.yaml` is a fixture list. Do not check a box from that file. Run these against the ingested PDF and record the result under `docs/phase10/runs/<timestamp>/`.

- [ ] One section contains the whole rule. Pass when every factual sentence cites that section and the quote contains the claim
- [ ] The same section contains an exception. Pass when the claim quotes the exception, along with the general rule
- [ ] A section points at another section. Pass when both sections are cited
- [ ] The answer needs two passages that do not point at each other. Pass when both are cited, or the turn refuses
- [ ] The rule depends on the season or the effective date. Pass when the answer names the passage it used, or asks which date the user means
- [ ] The quote states an operation and the question supplies every input. Pass when the number is the operation in the quote applied to those inputs, and the quote is cited
- [ ] The quote states an operation and one input is missing. Pass when the turn is `missing_inputs` and contains no computed number
- [ ] The question asks what a term means. Pass when the answer quotes the definition and does not add a number the quote does not contain
- [ ] The corpus has no passage for the question. Pass when the turn is `no_evidence` and has no factual claim
- [ ] Two passages match and neither says it controls. Pass when the turn is `ambiguous`, cites both, and does not pick a winner
- [ ] A draft claim cites a passage that does not contain the claim. Pass when that claim is dropped, and the turn refuses if no valid claim remains

**Exit:** each question either cites a retrieved passage that contains the claim, or refuses. No uncited factual claim.

## 11. Deploy

Default host is Railway, one frontend service and one backend service, until you name another.

- [ ] Frontend service (Vite static build) and backend service (Uvicorn) on that host
- [ ] Backend env: database URL, Supabase URL, anon key, service role, direct `DATABASE_URL`, answer-model key, embedding settings, production `ALLOWED_ORIGINS`
- [ ] Frontend env: API base URL only, until auth exists
- [ ] `alembic upgrade head` against the hosted database
- [ ] The auth site URL is the hosted frontend origin, and that origin is on the redirect allow-list, once phase 4 exists
- [x] README "Run the offline demo" has the local backend and frontend commands
- [ ] Smoke test on the deployed URL: ask one question, see an article, a section, and a page, reload

**Exit:** the smoke test passes on the hosted URL. The PDF is not in the deploy image and not in git.

## 12. UI fine touches

These wait until phase 11's exit passes.

- [ ] Citation chip copies the article, section, and page in one action
- [ ] Keyboard focus reaches the open passage and returns to the claim
- [ ] The thread list and the passage panel are usable at a narrow viewport
- [ ] A second hashed agreement, or a side letter, can be added as its own document without mixing its pages into the 2023 file. Do not build the comparison until phase 10 has passed on each file
- [ ] A transaction check that only cites the sections it used. Leave it until someone asks for it

**Exit:** a person can use the hosted app for a working session, ask one question, and verify the citation.

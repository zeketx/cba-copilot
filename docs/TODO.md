# CBA Copilot — build checklist

Work top to bottom. A phase is done only when its exit check passes.

The pilot corpus is one official PDF of the 2023 NBA collective bargaining agreement. Record its URL, file hash, cover date, and the printed term before any answer is shown to a person. Do not commit the PDF. Unofficial markdown, fan sites, and salary-cap explainers are not sources. A later agreement, a side letter, or an amendment is a separate document. It stays in phase 12 until this corpus passes phase 10.

The README proposes FastAPI, PydanticAI, Supabase pgvector, and hybrid reciprocal rank fusion. That is the recommended build path for the file names below. It is the shape named in the README and the shape of the sibling checklist this list follows. It is not a closed decision. Write the choice in `docs/stack.md` before phase 2. If you replace a piece, the later phases use that note instead of the recommendation.

The first user is not named. Recommendation: one person who must apply a printed rule and show a colleague the page. Email login is in this list so a second person cannot open the first person's threads.

`/Users/ezekielmauricio/Documents/dev/github/public/cba-copilot` is four unpushed commits ahead of `origin/main`. Do not check boxes from that checkout. This branch does not contain that demo.

## 0. Already in the repo

- [x] `README.md` names cited, refusal-first Q&A over the 2023 NBA CBA and proposes the stack above
- [x] `LICENSE`
- [x] `.cursor/settings.json` enables pstack
- [x] `.cursor/rules/grok-only.mdc`

The sibling checklist also checks an architecture note, a client brief, setup guides, backend dependencies, env examples, and a download script in this phase. Those files are not on this branch. They are unchecked tasks in phase 1 and phase 2.

## 1. Accounts and local corpus

- [ ] `docs/client-brief.md` states the user job as a recommendation until you name the person, the corpus rule above, what trust means (cite the passage or refuse), and what is out of the pilot
- [ ] `docs/architecture.md` states the request path, the evidence record, and the trust rules. Mark the README stack as recommended, not chosen, until `docs/stack.md` exists
- [ ] `docs/stack.md` either accepts the README proposal or names the replacement for the app server, the database, the embedding provider, the answer model, and the host. Record the embedding dimensions next to the model name
- [ ] `docs/guides/supabase-setup.md`, `docs/guides/backend-setup.md`, and `docs/guides/frontend-setup.md` match `docs/stack.md`
- [ ] `backend/pyproject.toml` and `frontend/package.json` exist for the chosen stack. The recommendation is Python 3.12, FastAPI, PydanticAI, Vite, React, TypeScript, and `pnpm`
- [ ] `backend/.env.example` and `frontend/.env.example` list every required variable and no secret
- [ ] Create the hosted database project named in `docs/stack.md` and turn on email auth. Disable confirm-email for local dev. Stop and ask before any paid project is created
- [ ] Copy credentials into `backend/.env` and `frontend/.env`. The service role and `DATABASE_URL` stay backend-only. Use the direct session URL for migrations, not the transaction pooler
- [ ] `data/download_cba.py` downloads the official PDF into `data/downloads/`. The PDF is gitignored. The script records the URL, the sha256, the cover date, and the printed term sentence in a gitignored manifest
- [ ] Do not vendor an unofficial markdown conversion. If a helper file is downloaded later, the manifest says it is not the source of truth, and every chunk still points at the official PDF page

**Exit:** `docs/stack.md` and the brief exist, both env files are filled, and `data/downloads/` contains the official PDF plus a manifest with its hash. A second download does not commit the PDF.

## 2. Boot both services

Backend (`docs/guides/backend-setup.md`):

- [ ] `app/config.py` is the only settings module. The process fails at startup if a required variable is missing. No `os.getenv` in app code
- [ ] `app/main.py` is the FastAPI app, with CORS from `ALLOWED_ORIGINS` and `GET /health`
- [ ] `uv run uvicorn app.main:app --reload` returns 200 from `/health`

Frontend (`docs/guides/frontend-setup.md`):

- [ ] Vite React TypeScript app, React Router, and the UI kit named in `docs/stack.md`. The recommendation is Tailwind and shadcn/ui. `pnpm` only
- [ ] `src/lib/env.ts` validates `VITE_API_BASE_URL` and the public auth settings named in `docs/stack.md`. The recommendation is `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`
- [ ] `src/lib/supabase.ts`, or the client named in `docs/stack.md`, creates the browser session
- [ ] App shell with routes for sign-in and chat. `pnpm tsc --noEmit` and `pnpm lint` pass

**Exit:** both processes run locally and the frontend can reach the backend health check.

## 3. Schema

Tables: `users`, `chat_threads`, `chat_messages`, `message_citations`, `source_documents`, `document_chunks`.

Recommendation, not a second schema. Signed-in users share the agreement. They do not share chats. Row policies keep each user on their own threads. Chunks are readable by every signed-in user.

- [ ] SQLAlchemy models in `app/database/models/`
- [ ] `alembic init`. `alembic/env.py` imports that metadata and reads `settings.DATABASE_URL`
- [ ] First migration in `alembic/versions/`, written from the models, with explicit SQL for:
  - [ ] `create extension if not exists vector`
  - [ ] an embedding column whose dimension is the number in `docs/stack.md`
  - [ ] generated `tsvector` on chunk text
  - [ ] HNSW index on the embedding
  - [ ] GIN indexes for full-text and JSON metadata
  - [ ] RLS so a user can only read and write their own chats, and can read the shared chunks
- [ ] `uv run alembic upgrade head` against the database named in `docs/stack.md`
- [ ] Chunk metadata can store the article number, the article title, the section as printed, the printed page, the PDF viewer page, the source URL, the order in the file, and the character offsets of the quote

**Exit:** `\dt` shows those tables, `vector` is installed, and a second `upgrade head` is a no-op.

## 4. Auth

- [ ] Email sign-up and sign-in in the SPA. The session stays in the shared auth client
- [ ] `app/auth/dependencies.py` verifies `Authorization: Bearer` and exposes `get_current_user`
- [ ] Reject a missing or invalid token with 401 before any retrieval or model call
- [ ] Create a `users` row for the signed-in user
- [ ] 403 when an authenticated user opens another user's thread

**Exit:** a signed-in request reaches a protected route. A request with no token gets 401.

## 5. Chat shell with a stubbed answer

This is the first end-to-end product slice. The assistant text can be a fixed string. The transport, the saved thread, and the UI state should be real.

- [ ] `src/lib/http.ts` sets the base URL, the bearer token, and timeouts, and types `ApiError` with a network-versus-HTTP flag
- [ ] `src/lib/api.ts` lists threads, creates a thread, and loads messages
- [ ] Thread list and new chat in the SPA. Only the current user's threads
- [ ] `POST /chat/stream` accepts `{ threadId, messages }` in the chat-UI message shape named in `docs/stack.md`. The recommendation is the AI SDK UI message shape
- [ ] Stream a stubbed assistant reply in that same event format
- [ ] The chat hook points at FastAPI with the access token. The recommendation is `useChat` and `DefaultChatTransport`
- [ ] After a successful run, persist the user message and the assistant message
- [ ] Reload shows the same thread history

**Exit:** sign in, send a message, watch it stream, refresh, and see it still there. A second user cannot open that thread.

## 6. Ingestion

- [ ] Parse the official PDF into text that keeps the source URL, the printed page, and the viewer page. Measure the offset between those two page numbers from the file. Do not assume an offset
- [ ] Upsert one `source_documents` row with that text, the source URL, the hash, the cover date, and the printed term (`uv run python -m ingestion` from `backend/`). A second run updates the same row
- [ ] Unit tests for the source-document load, with no network
- [ ] Chunk by article and section. Keep a section whole when it crosses a page. A page marker does not start a chunk. Store the article number, the article title, the section as printed, the chunk index, the token count, both page numbers, and the source offsets (`chunk_agreement` in `ingestion/chunk.py`)
- [ ] When a chunk tells the reader to apply another section, store that target on the chunk so retrieval can load the neighbor
- [ ] Embed chunks with the model and dimensions in `docs/stack.md`
- [ ] Upsert `document_chunks` (text, embedding, metadata). `search_vector` is generated by the database. A second `uv run python -m ingestion` does not add duplicate chunks
- [ ] Unit tests for chunking and the chunk insert, with no network (`uv run pytest tests/ingestion -q` from `backend/`)

**Exit:** the official PDF is queryable as rows in `source_documents` and `document_chunks`, with embeddings, both page numbers, and a populated `search_vector`. The PDF file is still gitignored.

## 7. Hybrid retrieval

Keep this independent of the answer model so it can be tested with fixed inputs.

- [ ] Embed the user query with the same model as the chunks
- [ ] Semantic search on `document_chunks.embedding`
- [ ] Lexical search on `document_chunks.search_vector`
- [ ] Fuse the two ranked lists in Python with reciprocal rank fusion. The sibling uses `k=60`. Use that value unless `docs/stack.md` sets another one (`reciprocal_rank_fusion`)
- [ ] Load the winning chunks, the previous and next section in the same article, a section targeted by a cross-reference, and the source-document metadata (`DocumentStore`)
- [ ] Bounded operations only: `search_sections`, `read_chunk`, `read_surrounding_chunks`. No model-written SQL
- [ ] Unit tests for fusion and for no hits (`tests/retrieval/`). A live check after ingestion returns the section you name, with its article, section, printed page, and viewer page

**Exit:** a fixture question returns the fixture passage. A question with no shared words returns no passages. Neither test calls a network.

## 8. Grounded agent

- [ ] `GroundedAnswer` and `Citation` join the retrieved passage on `chunk_id`. A citation carries the article number, the article title, the section as printed, both page numbers, and the quote
- [ ] The turn is an answer, a clarification, or a refusal. A refusal has a reason and no claims. It may still store the retrieved passage ids. The reasons are `no_support`, `ambiguous`, `missing_inputs`, and `citation_mismatch`
- [ ] `DocumentAgentDeps` carries `user_id`, `thread_id`, and this turn's retrieved passages
- [ ] The agent instructions require four behaviors. Answer only from retrieved passages. Cite every factual claim. Ask which season or effective date the user means when more than one passage applies and the question names neither. Refuse when the passages do not state the conclusion, including a number whose inputs are not all in the question or the quotes, and a choice between two clauses when neither says it controls
- [ ] `chat/orchestrator.py` streams one turn and persists it only after the validator accepts it
- [ ] The validator drops a claim whose passage id was not retrieved. If one valid claim remains, keep the answer and drop the bad claim. If none remain, refuse with `citation_mismatch`
- [ ] A failed validation returns a controlled error, and nothing is stored as a successful answer
- [ ] Stream text deltas first, then citation parts. Map auth, missing thread, retrieval, and grounding failures to 401, 403, 404, 422, and 502
- [ ] Tests, with no network and with fake quotes you write yourself. A citation must match a retrieved chunk. No hits are `no_support` with no claim. A missing season is a clarification whose claim ids were retrieved. An exception sentence in the same passage must appear in the claim, not only the general rule. A cross-reference answer cites both sections. Two matching passages with no controlling language are `ambiguous`, with both ids stored and no claim. Inputs `2` and `10` on a fake "multiply" fixture yield `20` only when both inputs are present. A missing input is `missing_inputs` and no computed number. Those fixture numbers are not agreement figures

**Exit:** one question you chose from `docs/client-brief.md` returns a cited answer through `POST /chat/stream`, and an off-corpus question returns `no_support`. The cited quote is contained in the retrieved passage.

## 9. Analyst UI

Analyst means the person named in `docs/client-brief.md`, not a role copied from another product.

- [ ] Render the answer, each citation (article, section, printed page, viewer page), and the underlying quote
- [ ] One click opens the passage the claim came from, at the viewer page of the official PDF
- [ ] Empty thread state, streaming state, and friendly errors for auth, network, and answer failure. A shared 502 is not labeled as a grounding refusal
- [ ] Rename and delete a chat from the sidebar
- [ ] Render assistant answer Markdown. Citations and user bubbles stay plain text
- [ ] Browser pass: sign in, ask, read a citation, open an old thread, rename, delete, sign out

**Exit:** a person can verify a claim from the citation without leaving the page.

## 10. Prove the brief

Run these against the ingested PDF and record the result under `docs/phase10/runs/<timestamp>/`. Check a box only when the saved run shows the pass condition. Do not check a box from this plan. Do not paste a legal conclusion into the run as if the checklist had supplied it.

- [ ] One section contains the whole rule. Pass when every factual sentence cites that section and the quote contains the claim
- [ ] The same section contains an exception. Pass when the claim includes the exception language, not only the general rule
- [ ] A section points at another section. Pass when both sections are cited
- [ ] The answer needs two passages that do not point at each other. Pass when both are cited, or the turn refuses
- [ ] The rule depends on the season or the effective date. Pass when the answer names the passage it used, or asks which date the user means
- [ ] The quote states an operation and the question supplies every input. Pass when the number is the operation in the quote applied to those inputs, and the quote is cited
- [ ] The quote states an operation and one input is missing. Pass when the turn is `missing_inputs` and contains no computed number
- [ ] The question asks what a term means. Pass when the answer quotes the definition and does not add a number the quote does not contain
- [ ] The corpus has no passage for the question. Pass when the turn is `no_support` and has no factual claim
- [ ] Two passages match and neither says it controls. Pass when the turn is `ambiguous`, cites both, and does not pick a winner
- [ ] A draft claim cites a passage that does not contain the claim. Pass when that claim is dropped, and the turn refuses if no valid claim remains

**Exit:** each question either cites a retrieved passage that contains the claim, or refuses. No uncited factual claim.

## 11. Deploy

The recommended host is Railway, one frontend service and one backend service, because that is the sibling's deploy shape. `docs/stack.md` can name another host before this phase starts.

- [ ] Frontend service (Vite static build) and backend service (Uvicorn) on the host named in `docs/stack.md`
- [ ] Backend env: database URL, auth URL, anon key, service role, direct `DATABASE_URL`, answer-model key, embedding settings, production `ALLOWED_ORIGINS`
- [ ] Frontend env: API base URL, auth URL, anon key only
- [ ] `alembic upgrade head` against the hosted database
- [ ] Production email confirmation turned back on
- [ ] The auth site URL is the hosted frontend origin, and that origin is on the redirect allow-list
- [ ] README "Running locally" filled in
- [ ] Smoke test on the deployed URL: sign in, ask one question, see an article, a section, and a page, reload history

**Exit:** the smoke test passes on the hosted URL. The PDF is not in the deploy image and not in git.

## 12. UI fine touches

These wait until phase 11's exit passes. They are not part of the pilot exit.

- [ ] Citation chip copies the article, section, and page in one action
- [ ] Keyboard focus reaches the open passage and returns to the claim
- [ ] The thread list and the passage panel are usable at a narrow viewport
- [ ] A second hashed agreement, or a side letter, can be added as its own document without mixing its pages into the 2023 file. Do not build the comparison until phase 10 has passed on each file
- [ ] A transaction check that only cites the sections it used. Recommendation, not a pilot feature. Leave it until the brief says the user needs it

**Exit:** the named pilot user can use the hosted app for a working session, ask one question, and verify the citation. There is no agreed hour-saved target.

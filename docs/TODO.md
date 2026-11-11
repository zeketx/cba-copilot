# CBA Copilot build checklist

Work top to bottom. A phase is done when its exit check passes.

The pilot is one official PDF of the 2023 NBA CBA. Record its URL, sha256, cover date, and printed term before a live answer is shown. Do not commit the PDF. Unofficial markdown, fan sites, and salary-cap explainers are not sources. A later agreement, side letter, or amendment stays in phase 12 until this PDF passes phase 10.

Checked boxes match `main` as of 2026-11-11. These PRs are on `main`: the scaffold ([#1](https://github.com/zeketx/cba-copilot/pull/1)), the corpus manifest ([#2](https://github.com/zeketx/cba-copilot/pull/2)), the bearer gate ([#4](https://github.com/zeketx/cba-copilot/pull/4), later landed on `main` with [#9](https://github.com/zeketx/cba-copilot/pull/9)), the embedding comparison harness ([#5](https://github.com/zeketx/cba-copilot/pull/5)), invite-only auth and ingest ([#9](https://github.com/zeketx/cba-copilot/pull/9)), the cap-inclusions label fix ([#8](https://github.com/zeketx/cba-copilot/pull/8)), Voyage 4 Lite at 1024 dimensions ([#10](https://github.com/zeketx/cba-copilot/pull/10)), per-definition chunking of Article I and the live-store eval ([#12](https://github.com/zeketx/cba-copilot/pull/12)), and full-path section labels ([#14](https://github.com/zeketx/cba-copilot/pull/14)). [#3](https://github.com/zeketx/cba-copilot/pull/3) was closed as superseded by [#9](https://github.com/zeketx/cba-copilot/pull/9), not merged. Issues [#6](https://github.com/zeketx/cba-copilot/issues/6), [#7](https://github.com/zeketx/cba-copilot/issues/7), [#11](https://github.com/zeketx/cba-copilot/issues/11), and [#13](https://github.com/zeketx/cba-copilot/issues/13) are closed. The hosted database has been migrated through `c0a2023b0007`. Default-deny RLS on `alembic_version` is on. The owner re-embedded 915 chunks at `vector(1024)` and reloaded labels after [#14](https://github.com/zeketx/cba-copilot/pull/14). The stack is in `AGENTS.md`. Corpus rules are in `docs/corpus.md`. The offline demo answers from a fixture and does not call a paid model.

## 0. Already in the repo

- [x] `README.md` describes cited, refusal-first Q&A over the 2023 NBA CBA ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `LICENSE` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `.cursor/settings.json` enables pstack ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `.cursor/rules/grok-only.mdc` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `AGENTS.md` names Python 3.12, FastAPI, PydanticAI, Vite, React, TypeScript, Tailwind, pnpm, Supabase pgvector, and `mongodb/voyage-4-lite` at 1024 dimensions ([#1](https://github.com/zeketx/cba-copilot/pull/1), updated in [#10](https://github.com/zeketx/cba-copilot/pull/10))
- [x] `docs/architecture.md` states the request path, the chunk record, and the trust rule ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `docs/corpus.md` states the official PDF, the gitignored download, the optional markdown aid, and the sources that stay out ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `docs/guides/supabase-setup.md`, `docs/guides/backend-setup.md`, and `docs/guides/frontend-setup.md` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `backend/pyproject.toml` and `frontend/package.json` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `backend/.env.example` and `frontend/.env.example` list the variables and contain no secrets ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `data/download_cba.py` saves the official PDF under `data/downloads/`, and the PDF is gitignored ([#1](https://github.com/zeketx/cba-copilot/pull/1))

## 1. Accounts and local corpus

- [x] Create the Supabase project in `docs/guides/supabase-setup.md` and stop before any paid project. The project is `nba-cba-copilot`, ref `wxfscyrhpqnbimjdqvyf`, region `us-east-2`. The public schema had no tables on 2026-11-08. Invite-only auth later landed in [#9](https://github.com/zeketx/cba-copilot/pull/9)
- [x] Copy credentials into `backend/.env`. The service role and `DATABASE_URL` stay backend-only. The URL uses `db.wxfscyrhpqnbimjdqvyf.supabase.co` on port 5432. A login as `postgres` succeeded on 2026-11-08. The file is gitignored
- [x] The download script records the URL, the sha256, the cover date, and the printed term in a gitignored manifest ([#2](https://github.com/zeketx/cba-copilot/pull/2)). `data/corpus.json` has the URL, the dates, and a printed-to-viewer offset of 24, and it has no hash
- [x] The unofficial markdown aid is not vendored. `data/download_markdown_aid.py` writes it only with `--i-accept-the-unofficial-aid`, and every chunk still needs the official PDF page ([#1](https://github.com/zeketx/cba-copilot/pull/1))

**Exit:** `backend/.env` is filled, and `data/downloads/` contains the official PDF plus a manifest with its hash. A second download does not commit the PDF.

## 2. Boot both services

Backend (`docs/guides/backend-setup.md`):

- [x] `app/config.py` is the only settings module. The offline demo starts with an empty env. Live mode raises when `DATABASE_URL` or `SUPABASE_URL` is missing. App code does not call `os.getenv` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `app/main.py` is the FastAPI app. CORS reads `ALLOWED_ORIGINS`. Health is `GET /api/health` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `uv run uvicorn app.main:app --host 127.0.0.1 --port 8011` returns 200 from `/api/health` with `{"ok":"true","mode":"fake"}`. Port 8000 was already taken by another local app, so this proof did not use 8000

Frontend (`docs/guides/frontend-setup.md`):

- [x] Vite, React, TypeScript, Tailwind, and shadcn/ui. pnpm only. One screen, no router. The dev server proxies `/api` to `http://127.0.0.1:8000` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `pnpm typecheck` and `pnpm lint` passed on 2026-11-08

**Exit:** both processes run locally and the frontend can reach `/api/health`. On 2026-11-08 the proof used backend port 8011 and frontend port 5174, because 8000 and 5173 were already in use. The committed Vite proxy still points at `http://127.0.0.1:8000`. The proxied health body was `{"ok":"true","mode":"fake"}`.

## 3. Schema

`source_documents`, `cba_chunks`, `users`, `chat_threads`, `chat_messages`, and `message_citations` are on the hosted database. Auth is in the app ([#9](https://github.com/zeketx/cba-copilot/pull/9)). Row policies for the chat tables are still open.

- [x] SQLAlchemy models in `app/database/models.py` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `alembic/env.py` imports that metadata and reads `Settings().sqlalchemy_database_url` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] First migration in `alembic/versions/c0a2023b0001_cba_schema.py` ([#1](https://github.com/zeketx/cba-copilot/pull/1)) creates:
  - [x] `create extension if not exists vector`
  - [x] an embedding column, now `vector(1024)` after `c0a2023b0007` ([#10](https://github.com/zeketx/cba-copilot/pull/10)). It was 1536 in `c0a2023b0001`
  - [x] generated `tsvector` on chunk text
  - [x] HNSW index on the embedding, rebuilt in `c0a2023b0007`
  - [x] GIN index on `search_vector`
- [x] GIN index on JSON metadata, in `c0a2023b0002_chunk_pages_and_rls.py`. Applied to the hosted database on 2026-11-09
- [x] Chat tables in `c0a2023b0003_chat_tables.py` ([#9](https://github.com/zeketx/cba-copilot/pull/9); [#3](https://github.com/zeketx/cba-copilot/pull/3) was closed as superseded). Applied to the hosted database on 2026-11-09
- [ ] Row policies for the chat tables. The tables enable row level security and revoke `anon` and `authenticated`. No policy is created. `c0a2023b0006` in [#9](https://github.com/zeketx/cba-copilot/pull/9) adds the same default-deny treatment to `alembic_version` only
- [x] `source_documents` and `cba_chunks` enable row level security and revoke `anon` and `authenticated`. No row policy is created. Applied to the hosted database on 2026-11-09
- [x] `uv run alembic upgrade head` against the hosted database. Head is `c0a2023b0007`. Applied live after [#10](https://github.com/zeketx/cba-copilot/pull/10). `vector` is installed. The public tables are `source_documents`, `cba_chunks`, `users`, `chat_threads`, `chat_messages`, and `message_citations`
- [x] A chunk can store the article number, the article title, the section, the page range, the source URL, the order in the file, and the token count ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] Store the printed page and the viewer page as separate fields, and store the character offsets of the quote, in the model and in `c0a2023b0002`. Ingest fills both page numbers. It does not fill the quote offsets yet

**Exit:** `\dt` shows the corpus tables and the chat tables, `vector` is installed, and a second `upgrade head` is a no-op.

## 4. Auth

Access is invite-only ([#9](https://github.com/zeketx/cba-copilot/pull/9)). Public sign-up stays off until the owner opens it. A visitor can leave an email to request access. That request does not create an account. The owner sends the invite from Authentication, then Users, then Add user, then Send invitation. That control is not on Project Overview. A row in `public.users` does not send an invite. Supabase rejects a new account that was not invited. The app also rejects a signed-in email that is not on the allow-list. The link in the invite email does not open this app yet. Until the phase 11 redirect exists, an invited person uses Send code.

- [x] A public form takes an email and stores an access request. It does not create a user ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9)). `c0a2023b0004` is on the hosted database. On 2026-11-10 `POST /api/access-requests` returned 200, a second post kept the same `created_at`, and that request did not add a `users` row
- [x] Email sign-in in the SPA for an invited address. No public sign-up form. The dialog sends a code with `create_user` false ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9)). A live code has not been received yet, because the dashboard invite has not been sent
- [x] `app/auth/dependencies.py` verifies `Authorization: Bearer` and exposes `get_current_user` ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] Reject a missing or invalid token with 401 before any retrieval or model call ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9)). The offline test is `test_rejected_bearer_does_not_call_the_pipeline`. A live missing token returned 401 on 2026-11-10
- [x] Reject a signed-in email that is not on the allow-list with 403 ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9)). The offline test is `test_unlisted_email_does_not_insert_a_user`. A live signed-in 403 has not been run
- [x] Create a `users` row for an allowed signed-in user. `AccessGate.admit` inserts `users.id` after the allow-list check ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9)). Offline tests use the memory ledger
- [x] 403 when an authenticated user opens another user's thread ([#9](https://github.com/zeketx/cba-copilot/pull/9)). `GET /api/threads/{thread_id}` loads the owner and builds `ThreadGrant`. A missing thread is 404. The offline test is `test_opening_another_users_thread_is_forbidden`

**Exit:** an invited person reaches a protected route. A request with no token gets 401. A person who was not invited gets 403. The 401 is proven. The invited sign-in is not, because the dashboard invite has not been sent.

## 5. Chat shell

The screen lists the signed-in user's threads, streams a reply, and reloads that history. The screen uses Beautiful UI (`https://www.beautifului.dev/`): the foundation theme, `Button`, `StreamText`, `ContextCards`, and `LoadingState`.

- [x] The screen calls `POST /api/ask` with `{ question }` and renders each claim or a refusal ([#1](https://github.com/zeketx/cba-copilot/pull/1); bearer gate in [#4](https://github.com/zeketx/cba-copilot/pull/4))
- [x] The empty screen says fixture mode. It says replies use the checked-in demo passages and are not a live reading of the official PDF ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `src/lib/http.ts` sets the base URL, the bearer token, and timeouts, and types `ApiError` with a network-versus-HTTP flag. Access requests and ask go through it. Sign-in still calls Supabase directly ([#4](https://github.com/zeketx/cba-copilot/pull/4), on `main` via [#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] `src/lib/api.ts` lists threads, creates a thread, and loads messages ([#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] Thread list and new chat. Only the current user's threads ([#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] `POST /api/chat/stream` accepts `{ threadId, messages }` and streams the assistant reply ([#9](https://github.com/zeketx/cba-copilot/pull/9)). The checklist name was `/chat/stream`. The route lives under `/api` with the other routes
- [x] After a successful run, persist the user message and the assistant message ([#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] Reload shows the same thread history ([#9](https://github.com/zeketx/cba-copilot/pull/9))

**Exit:** sign in, send a message, watch it stream, refresh, and see it still there. A second user cannot open that thread. On 2026-11-10 the browser sent a fixture question, showed the reply and the citation chips, and kept that thread after refresh. The button read Asking while the reply was on the way. `test_list_does_not_include_another_users_thread` returns 403 for the other user. The browser session used a test token. A dashboard invite is still required for a live sign-in.

## 6. Ingestion

- [x] Parse the official PDF into text that keeps the source URL, the printed page, and the viewer page. Measure the offset from the file. Do not assume an offset. `ingest/pdf.py` reads the printed page from each running header ([#9](https://github.com/zeketx/cba-copilot/pull/9)). All 560 article pages give an offset of 24. Exhibits, viewer pages 585 to 676, are not ingested yet
- [x] Upsert one `source_documents` row with that text, the source URL, the hash, the cover date, and the printed term. A second run updates the same row. Migration `c0a2023b0005` adds the columns and a unique `source_url` ([#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] `chunk_markdown` in `ingest/chunker.py` chunks by article and section, keeps a section whole across a page, and does not start a chunk on a page marker. Article I definitions are one chunk per lettered definition ([#12](https://github.com/zeketx/cba-copilot/pull/12)). Section labels keep the full parent path, and known PDF word splits are rejoined in the section column only ([#14](https://github.com/zeketx/cba-copilot/pull/14)). Tests are in `tests/test_chunker.py` and do not use the network
- [x] When a chunk tells the reader to apply another section, store that target on the chunk. Targets live in `chunk_metadata.references` as `{article, section}` ([#9](https://github.com/zeketx/cba-copilot/pull/9))
- [x] Compare embedders by recall and cost with `python -m evals.embed_bench` ([#5](https://github.com/zeketx/cba-copilot/pull/5)). The chosen live model is `mongodb/voyage-4-lite`
- [x] Embed chunks with `mongodb/voyage-4-lite` at 1024 dimensions ([#10](https://github.com/zeketx/cba-copilot/pull/10)). From `backend/`, run `uv run alembic upgrade head`, then `uv run python -m ingest embed --live`. The command needs `OPENROUTER_API_KEY`. Without `--live` it exits and sends no request. An agent session may not call OpenRouter, so the owner runs it. The owner ran it: 915 chunks are stored at `vector(1024)`
- [x] Upsert `cba_chunks`. `search_vector` is generated by the database. A second ingest does not add duplicate chunks ([#9](https://github.com/zeketx/cba-copilot/pull/9))

**Exit:** the official PDF is queryable as rows in `source_documents` and `cba_chunks`, with embeddings, both page numbers, and a populated `search_vector`. The PDF file is still gitignored. On 2026-11-10 two `ingest load` runs left one document and 857 chunks with the same ids. After the Article I split and the label reload, the live store has 915 chunks with Voyage embeddings at 1024 dimensions. Every chunk has both page numbers and a populated `search_vector`. Exhibits, viewer pages 585 to 676, are still not ingested.

## 7. Hybrid retrieval

- [x] `reciprocal_rank_fusion` uses `k=60` unless `RETRIEVAL_RRF_K` sets another value ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] `vector_search_sql` and `keyword_search_sql` are fixed statements. No model-written SQL ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] The offline store fuses a hash embedding and keyword overlap. `tests/test_fusion.py` and `tests/test_retrieval.py` do not call the network ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] Embed the user query with the same model used for the stored chunks ([#10](https://github.com/zeketx/cba-copilot/pull/10)). Live OpenRouter calls use `input_type` `query`. The fixture `/api/ask` path keeps the hash embedder
- [x] Run the vector search and the lexical search on `cba_chunks` after ingest ([#12](https://github.com/zeketx/cba-copilot/pull/12)). `PostgresChunkStore` runs the fixed SQL, and `evals.embed_bench --database` scores the live store
- [x] Load the winning chunks, the previous and next section in the same article, a section targeted by a cross-reference, and the source-document metadata ([#16](https://github.com/zeketx/cba-copilot/pull/16)). Neighbors stay in the same article. A cross-reference that names no stored section is skipped. Context passages count as retrieved, and the fused hits keep their rank
- [x] A live check returns the section you name, with its article, section, printed page, and viewer page. The live-store eval landed in [#12](https://github.com/zeketx/cba-copilot/pull/12) and was re-run after [#14](https://github.com/zeketx/cba-copilot/pull/14). The post-merge eval reported LENIENT draft hybrid R@5 of 1.000 and all-questions R@5 of 0.943. Remaining misses are in Follow-ups

**Exit:** a fixture question returns the fixture passage. A question with no shared words returns no passages. Neither test calls a network. The live check names a real section from the ingested PDF.

## 8. Grounded agent

- [x] `validate_draft` keeps a claim only when every passage id was retrieved. If one valid claim remains, that claim stays. If none remain, the reason is `citations_dropped` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] No claims, or `insufficient_evidence`, refuses with `no_evidence` ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] Tests in `tests/test_grounding.py` and `tests/test_agent.py` use stand-in models and do not call the network ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] Add `ambiguous` and `missing_inputs`. Ask which season or effective date applies when more than one passage matches and the question names neither ([#17](https://github.com/zeketx/cba-copilot/pull/17))
- [ ] Persist the turn only after the validator accepts it
- [ ] Stream text deltas first, then citation parts. Map auth, missing thread, retrieval, and grounding failures to 401, 403, 404, 422, and 502

**Exit:** one question from `backend/evals/questions.yaml` returns a cited answer through the API, and an off-corpus question returns `no_evidence`. The cited quote is contained in the retrieved passage.

## 9. Analyst UI

- [x] The demo renders each claim and a chip with the article, the section, and the page ([#1](https://github.com/zeketx/cba-copilot/pull/1))
- [x] A click opens a source panel for that passage ([#1](https://github.com/zeketx/cba-copilot/pull/1))
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
- [ ] Frontend env: API base URL only. Auth already exists in the app
- [ ] `alembic upgrade head` against the hosted database
- [ ] The auth site URL is the hosted frontend origin, and that origin is on the redirect allow-list, so the invite link opens this app. Until this box is done, an invited person uses Send code
- [x] README "Run the offline demo" has the local backend and frontend commands ([#1](https://github.com/zeketx/cba-copilot/pull/1))
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

## Follow-ups

These are open after the work merged on the evening of 2026-11-10. They are not a new phase.

- [x] Add to the eval docs: LENIENT scoring with the text guard is the eval gate; STRICT is still reported. Noted in `docs/embedding-bench.md` in #15
- [ ] Retrieval and question-design follow-up for `second-apron-trade` and `cap-inclusions` in `backend/evals/questions.yaml`. The `2(e)` label on `second-apron-trade` is verified against the CBA (Article VII 2(e)(4) transaction table, printed page 187); the miss is real, not a bad label. `cap-inclusions` needs both Article I 1(lll) and Article VII 4
- [ ] Review the 30 draft questions in `backend/evals/draft_questions.yaml`

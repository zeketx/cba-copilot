# Why this checklist is shaped this way

This note explains the choices in [TODO.md](TODO.md). The checklist itself is the how-to. Nothing in that list is built on `origin/main`.

## What the repo actually contains

`origin/main` is `a7c5a1d`. Its tracked files are `README.md`, `LICENSE`, `.cursor/settings.json`, and `.cursor/rules/grok-only.mdc`. The README is one sentence. It proposes cited, refusal-first Q&A over the 2023 NBA CBA, and it names FastAPI, PydanticAI, Supabase pgvector, and hybrid reciprocal rank fusion. Local `.cursor/settings.json` on that commit has `plugins.pstack.enabled` set to true.

`/Users/ezekielmauricio/Documents/dev/github/public/cba-copilot` is a separate checkout of the same remote. Its `main` is four commits ahead of `origin/main`, author Cursor Agent, dated 2026-10-29, and those commits are unpushed. They contain an offline demo and extra docs. This branch does not use that demo as the baseline, and this session did not modify that checkout.

`zeketx/document-copilot` is a different product. It was not edited.

## OpenCode did not produce a draft

The CLI is `/Users/ezekielmauricio/.opencode/bin/opencode`, version `opencode v2.2.4`. `opencode service status` reported `http://127.0.0.1:49374`. PIDs 34465 (`opencode serve --service`) and 23981 (the desktop TUI on `ttys000`) were still running after these calls. The saved default model was left at `opencode/deepseek-v4.1-flash-free`. No `--model`, `--continue`, `--standalone`, or `--auto` flag was passed. The password in the service config was not read.

The first call passed `--server http://127.0.0.1:49374` and a UUID session id. It failed before a session existed. The error said the server requires a password in `OPENCODE_PASSWORD`.

The second call omitted `--server`, so the local client could use the already running service. It failed because the session id did not start with `ses`.

The third call used session `ses_c9443b8b90144de08d92b640724546e8`, agent `plan`, and `--format json`. The server started the session and then returned `provider.free-limit`, HTTP 429. The message said the free usage limit was reached.

A fourth call, session `ses_ed5c9e391def4836a3512f21a386cfc3`, asked for a one-word reply and got the same 429. There is no OpenCode draft text to accept or reject. The model was not switched, and no new provider or paid plan was added.

## Independent review

One Cursor review used `grok-4.7-medium-fast` as a fresh `generalPurpose` agent, id `bc-c91257d8-a600-5200-abae-d8910f0765b8`. `poteto-agent` was not in the available agent list. The repo rule and the request both limit Cursor helpers to one Grok pass, so there was no multi-family panel. The reviewer did not see an OpenCode draft, because none exists. The reviewer read the checklist and returned accepts and rejects. No numeric score was asked for or used.

Accepted from that review, and now in the checklist.

- The evidence record stays ahead of any store or drafter. The reviewer would not scrap that sequence. A database or a model before the fixture tests would lock the README proposal too early.
- Task 3 now accepts a clarification when the season is missing, and every claim id on it has to be retrieved.
- A bad citation is dropped. One remaining valid claim stays an answer. A refusal with `citation_mismatch` happens only when every claim is bad.
- An `ambiguous` refusal stores both passage ids and an empty claim list.
- The load test fails when any required passage field is removed. Task 2 looks up a printed page with no network.
- Task 4 has a same-section exception fixture. Task 5 accepts the dated-passage case in both directions.
- `outside_corpus` was removed until a task defines it. Lookup is by article number and section as printed.
- Task 8 is the first check against the hashed PDF. The official sentences stay in a gitignored transcript. The commit records the hash, the location, and the outcome type.

That last limit is narrower than the review's wording. The review asked for the quote in the transcript. The transcript has the quote. Git does not, because this public repo should not gain official agreement text in the same step that refuses to commit the PDF.

No invented legal conclusion was found by the review. None was added after it.

## Recommendations left open

The first user is a recommendation, not an interview. One person applies a printed rule and shows the page. Zeke can name someone else.

The authoritative text is a recommendation, not a verified download. One official PDF, hashed, is the corpus. The 676-page July 2023 description lives only in the unpushed checkout and was not opened here.

The proposed latency bar is under 2 seconds for a fixture question with zero model calls, on a laptop, with no network. That number is not a measurement.

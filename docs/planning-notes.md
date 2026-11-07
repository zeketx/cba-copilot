# Why the checklist follows the sibling build list

[TODO.md](TODO.md) replaces the shorter plan. That shorter plan was rejected. The requested format is the live build checklist at [docs/todos.md on main](https://github.com/zeketx/document-copilot/blob/abaa5e6f211fde14ac9c4ffb40f965bf93cade96/docs/todos.md).

The file blob is `f000f55f1cc4857b0367845299484dec7982ae49`. The last commit on `main` that changed it is `abaa5e6f211fde14ac9c4ffb40f965bf93cade96` (2026-10-25, "Record the brief retest and show the model the full chunk."). This note was written from that GitHub file. The local `document-copilot` checkout was not fetched or edited. It is 37 commits behind `origin/main`.

## Headings in the reference

The reference title is `# Document Copilot — build checklist`.

The phase headings are:

- `## 0. Already in the repo`
- `## 1. Accounts and local corpus`
- `## 2. Boot both services`
- `## 3. Schema`
- `## 4. Auth`
- `## 5. Chat shell with a stubbed answer`
- `## 6. Ingestion`
- `## 7. Hybrid retrieval`
- `## 8. Grounded agent`
- `## 9. Analyst UI`
- `## 10. Prove the brief`
- `## 11. Deploy`
- `## 12. UI fine touches`

Each phase from 1 through 12 ends with a bold exit line. Phase 3 nests the migration SQL. Tasks name files and commands. Phase 10 is a list of proof questions. The reference also has a results log for questions that were already run. This CBA list does not invent that log.

The sibling architecture and client brief were read only to see how the checklist points at them. Their SEC requirements are not copied. Architecture headings used for that reading start at Purpose, High-Level Architecture, Architectural Goals, Stack, System Boundaries, Request Flow, Frontend Chat Layer, Backend LLM Layer, Retrieval Strategy, Supabase and FastAPI Communication, Streaming Contract, Data Model, Schema Management, Grounding and Citation Policy, Error Handling, Configuration, Deployment Shape, Implementation Sequence, and Non-Goals. The brief headings start at The client, How Driftwood makes money, How they add value, The problem, What they want, Example analyst questions, What "trust" means here, Constraints, Out of scope (explicitly), and Definition of done.

## How the phases map

| Reference phase | CBA phase | What changed |
| --- | --- | --- |
| 0. Already in the repo | Same heading | Only README, LICENSE, pstack, and the Grok rule are checked. The sibling's guides and app scaffold are still tasks. |
| 1. Accounts and local corpus | Same heading | The corpus is one official PDF, hashed and gitignored. `docs/stack.md` records the stack choice before phase 2. |
| 2. Boot both services | Same heading | Health check and both apps. Names follow `docs/stack.md`. |
| 3. Schema | Same heading | Shared agreement, private chats. Metadata is article, section, and both page numbers. |
| 4. Auth | Same heading | Email session, 401, and 403. The user is still a recommendation. |
| 5. Chat shell with a stubbed answer | Same heading | Stub text, real thread, real stream. |
| 6. Ingestion | Same heading | Chunk by article and section. Measure the printed-page offset from the file. |
| 7. Hybrid retrieval | Same heading | Same two searches and fusion. Neighbors include a cross-reference target. `k=60` is the sibling default, not a measured CBA constant. |
| 8. Grounded agent | Same heading | Answer, clarification, or refusal. Missing inputs and ambiguity are reasons. Fixture arithmetic uses fake inputs. |
| 9. Analyst UI | Same heading | Analyst means the person in the brief. The citation shows article, section, and page. |
| 10. Prove the brief | Same heading | Eleven proof types, all unchecked. No pasted legal conclusion and no timing log. |
| 11. Deploy | Same heading | Host and smoke test stay in the list. Railway is the recommendation, not a purchase. |
| 12. UI fine touches | Same heading | Small UI tasks, then a second hashed document and a transaction check. Those last two wait until the pilot exit. |

## Decisions that are still recommendations

The first user is one person who must show a colleague the printed page. You can name someone else in the brief.

The authoritative text is one official 2023 PDF. Its hash, cover date, and term are recorded from the file during phase 1. A 676-page July 2023 description exists only in the unpushed checkout and was not opened for this rewrite.

The README stack is the recommended path so the tasks can name files. `docs/stack.md` is the place to reject a piece before phase 2. OpenAI, 1536 dimensions, Railway, and `k=60` are sibling defaults named as recommendations. They are not agreed CBA requirements.

There is no agreed saved-hours target.

## OpenCode and the review

This checklist was not written by OpenCode.

`opencode v2.2.4` was called once for this rewrite. `opencode service status` was `http://127.0.0.1:49374`. Session `ses_da8f6a9d59ed4bdb930ce7a35ac5756e`, agent `plan`, no `--model`, no `--continue`, no `--standalone`, no `--auto`. The server started the session and returned `provider.free-limit`, HTTP 429. The saved model was still `opencode/deepseek-v4.1-flash-free`. There was no second attempt and no model change. PIDs 34465 and 23981 were still running. An earlier rewrite attempt in this project failed the same way on sessions `ses_c9443b8b90144de08d92b640724546e8` and `ses_ed5c9e391def4836a3512f21a386cfc3`.

One Cursor review used `grok-4.7-medium-fast`, agent `bc-3708ec08-aaf6-54b6-8b49-be29c762aa22`. It accepted the phase order, the exit lines, the nested migration boxes, and the unchecked phase 10 list. It rejected three lines, and those edits are in `TODO.md`.

- Phase 9 is titled `Analyst UI`, with one sentence that the word means the person in the brief.
- The schema task no longer names a filing ticker or an accession number.
- The intro no longer says phase 4 can be skipped. Phase order is the dependency.

The review found no invented legal answer. The four checked boxes are the files on this branch.

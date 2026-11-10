# Set up a new Supabase project

CBA Copilot has its own Supabase project. Do not reuse a document-copilot database, and do not create a second project. v1 has no auth. The backend uses the direct Postgres connection.

## Project already created

Checked on 2026-11-08. The project was `ACTIVE_HEALTHY`.

| Fact | Value |
| --- | --- |
| Name | `nba-cba-copilot` |
| Project ref | `wxfscyrhpqnbimjdqvyf` |
| Organization | `vercel_icfg_6dsUaBiAE34aGjsPu4BjL7r3` |
| Region | `us-east-2` |
| API URL | `https://wxfscyrhpqnbimjdqvyf.supabase.co` |
| Direct host | `db.wxfscyrhpqnbimjdqvyf.supabase.co` port 5432 |
| Public tables | none |

The quoted cost at creation was $0 for the month. Do not upgrade the project from this repo. The database password and the service role key are not in git.

## Create the project

Skip this section. The project above already exists.

1. Open [supabase.com](https://supabase.com) and sign in.
2. Open the project `nba-cba-copilot`, not New project.
3. Leave the name, region, and ref as they are.

## Copy the connection values

| Value | Where | Used by |
| --- | --- | --- |
| Project URL | Project Settings, API | `SUPABASE_URL` |
| anon key | Same page | `SUPABASE_ANON_KEY` |
| service_role key | Same page | `SUPABASE_SERVICE_ROLE_KEY`, backend only |
| Direct connection string | Project Settings, Database | `DATABASE_URL` |

Use the direct host `db.wxfscyrhpqnbimjdqvyf.supabase.co` on port 5432. Alembic needs that session connection. Do not use the transaction pooler for migrations.

URL-encode special characters in the password.

Put the values in `backend/.env`. That file is gitignored. `backend/.env.example` lists the names with placeholders.

## Apply the schema

Phase 3 owns this step. Do not run it while `DATABASE_URL` is empty.

From `backend/`:

```bash
uv run alembic upgrade head
```

The migration creates the `vector` extension, `source_documents`, `cba_chunks`, a generated `search_vector` column, an HNSW index on `embedding`, and a GIN index on `search_vector`.

`uv run alembic upgrade head` also creates `users`, `chat_threads`, `chat_messages`, and `message_citations`, enables row level security, and creates no policies.

Do not create these tables by hand in the dashboard.

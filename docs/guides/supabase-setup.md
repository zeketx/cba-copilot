# Set up a new Supabase project

Create a new project for CBA Copilot. Do not reuse a document-copilot database. v1 has no auth. The backend uses the direct Postgres connection.

## Create the project

1. Open [supabase.com](https://supabase.com) and sign in.
2. Open [New project](https://supabase.com/dashboard/new).
3. Name the project `cba-copilot`.
4. Save the database password.
5. Choose a region near you and create the project.

## Copy the connection values

| Value | Where | Used by |
| --- | --- | --- |
| Project URL | Project Settings, API | `SUPABASE_URL` |
| anon key | Same page | `SUPABASE_ANON_KEY` |
| service_role key | Same page | `SUPABASE_SERVICE_ROLE_KEY`, backend only |
| Direct connection string | Project Settings, Database | `DATABASE_URL` |

Use the direct host `db.<project-ref>.supabase.co` on port 5432. Alembic needs that session connection. Do not use the transaction pooler for migrations.

URL-encode special characters in the password.

Put the values in `backend/.env`. That file is gitignored. `backend/.env.example` lists the names with placeholders.

## Apply the schema

From `backend/`:

```bash
uv run alembic upgrade head
```

The migration creates the `vector` extension, `source_documents`, `cba_chunks`, a generated `search_vector` column, an HNSW index on `embedding`, and a GIN index on `search_vector`.

Do not create these tables by hand in the dashboard.

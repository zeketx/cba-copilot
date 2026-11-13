# Point the hosted app at the backend role

The hosted backend must connect as `cba_copilot_app`, not as `postgres`. That role can read the 2023 CBA tables and can read and write the chat tables. Migrations stay on `postgres`. This guide does not create row policies. Chat tables already revoke `anon` and `authenticated`. Only this backend role is granted table access.

## Create the role

1. Open the SQL editor as `postgres` on project `nba-cba-copilot`.
2. Paste `backend/scripts/app_role.sql` and run it.
3. Set a password for `cba_copilot_app` in the dashboard or with `ALTER ROLE`. Do not put that password in git.

A second run of the script leaves the same grants. It does not create a second role.

Run this script only with the owner's go-ahead. Set the password as a SCRAM verifier or in the dashboard so the plain password never reaches SQL logs. Do not grant `SUPERUSER`. Do not use `service_role` as `DATABASE_URL`.

`cba_copilot_app` has `BYPASSRLS` so its grants work while row level security stays on with no policies. That is not superuser. `anon` and `authenticated` still have no row access.

## Host `DATABASE_URL`

Put the direct session URL in the hosted backend env, with this role as the user:

```text
postgresql://cba_copilot_app:<password>@db.wxfscyrhpqnbimjdqvyf.supabase.co:5432/postgres
```

Use host `db.wxfscyrhpqnbimjdqvyf.supabase.co` on port 5432. Do not use the transaction pooler. URL-encode special characters in the password.

Keep `SUPABASE_SERVICE_ROLE_KEY` for Auth API calls only. The SQLAlchemy engine uses `DATABASE_URL`.

## Keep Alembic on `postgres`

From a machine that has the `postgres` password, run:

```bash
uv run alembic upgrade head
```

Leave that `DATABASE_URL` on `postgres` for the upgrade. After the upgrade, the hosted app still uses `cba_copilot_app`.

## Grants

| Tables | Privileges |
| --- | --- |
| `source_documents`, `cba_chunks` | `SELECT` |
| `users`, `chat_threads`, `chat_messages`, `message_citations`, `access_requests` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |

The script does not grant on `alembic_version`. It does not create a policy.

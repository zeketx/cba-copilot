# Deploy to Railway

The hosted app is Railway project `cba-copilot`, environment `production`, region `us-east4`.

| Service | URL | Build |
| --- | --- | --- |
| `frontend` | <https://cba-copilot.up.railway.app> | `frontend/Dockerfile`, `vite preview` on `$PORT` |
| `backend` | <https://cba-copilot-api.up.railway.app> | `backend/Dockerfile`, Uvicorn on `$PORT`, healthcheck `/api/health` |

Both images build from the repository root, because the app reads `data/corpus.json` and `definitions/`. The PDF is not copied into either image.

## Ship a commit

Both services are pinned to one `main` commit. A push to `main` does not deploy. To ship, reconnect each service to `zeketx/cba-copilot` at the new commit in the Railway dashboard (Settings, Source), or with the Railway MCP `connect-service-source` and `commitSha`. Roll back from the service's Deployments tab.

## Variables

Backend: `PORT`, `ENVIRONMENT=production`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `ANSWER_PROVIDER`, `ANSWER_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `ALLOWED_ORIGINS`, `ALLOWED_EMAILS`.

- `DATABASE_URL` uses the direct host `db.wxfscyrhpqnbimjdqvyf.supabase.co:5432` as `cba_copilot_app` (see `database-role.md`). That host is IPv6-only, so the backend has Railway outbound IPv6 turned on.
- `SUPABASE_SERVICE_ROLE_KEY` is not set. No backend code reads it.
- `ALLOWED_EMAILS` is the list of people who may use the app. Add an email there, then redeploy.

Frontend: `PORT`, `VITE_API_BASE`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. The `VITE_` values are public and baked in at build time. `vite preview` answers only `RAILWAY_PUBLIC_DOMAIN`, any host in `PREVIEW_ALLOWED_HOSTS`, and Railway's healthcheck host.

## Supabase Auth settings (dashboard only)

1. Authentication, URL Configuration: Site URL `https://cba-copilot.up.railway.app`. Redirect URLs: add `https://cba-copilot.up.railway.app/**`.
2. Authentication, Emails, Templates: the dialog asks for a code. Put `{{ .Token }}` in both **Confirm signup** and **Magic Link**, for example `<p>Your CBA Copilot code: <strong>{{ .Token }}</strong></p>`.
3. Optional: Authentication, Emails, SMTP Settings. Use a custom sender such as Resend. The default sender has a low hourly limit.

## Check a deploy

```bash
curl https://cba-copilot-api.up.railway.app/api/health   # {"ok":"true","mode":"live"}
curl -I https://cba-copilot-api.up.railway.app/docs       # 404 in production
curl -I https://cba-copilot.up.railway.app/               # CSP, HSTS, X-Frame-Options DENY
```

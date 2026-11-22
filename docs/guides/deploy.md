# Deploy to Railway

The hosted app is Railway project `cba-copilot`, environment `production`, region `us-east4`.

| Service | URL | Build |
| --- | --- | --- |
| `frontend` | <https://cba-copilot.up.railway.app> | `frontend/Dockerfile`, `vite preview` on `$PORT` |
| `backend` | <https://cba-copilot-api.up.railway.app> | `backend/Dockerfile`, Uvicorn on `$PORT`, healthcheck `/api/health` |

Both images build from the repository root, because the app reads `data/corpus.json` and `definitions/`. The PDF is not copied into either image.

## Ship a commit

Merges to `main` auto-deploy `frontend` and `backend` on Railway (trigger branch: `main`).

- `frontend` watch paths: `frontend/**`, `data/corpus.json`
- `backend` watch paths: `backend/**`, `data/corpus.json`, `definitions/**`

If a trigger misses, reconnect the service with the Railway MCP `connect-service-source` using repo `zeketx/cba-copilot` and branch `main`, and do not pass `commitSha`. Roll back from the service's Deployments tab.

`retrieval-bench` stays pinned to a commit and must never be reconnected without `commitSha`, because it is a paid bench.

## Variables

Backend: `PORT`, `ENVIRONMENT=production`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `ANSWER_PROVIDER`, `ANSWER_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `ALLOWED_ORIGINS`, `ALLOWED_EMAILS`.

- `DATABASE_URL` uses the direct host `db.wxfscyrhpqnbimjdqvyf.supabase.co:5432` as `cba_copilot_app` (see `database-role.md`). That host is IPv6-only, so the backend has Railway outbound IPv6 turned on.
- `SUPABASE_SERVICE_ROLE_KEY` is not set. No backend code reads it.
- Admission reads `public.allowed_emails`. Approve someone by inserting a row in the Supabase table editor. That insert should create the auth user if missing. It does not send a login link.
- `ALLOWED_EMAILS` is an emergency add-only override. It cannot block a database-approved email. It is not required after the table is seeded.

Frontend: `PORT`, `VITE_API_BASE`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. The `VITE_` values are public and baked in at build time. `vite preview` answers only `RAILWAY_PUBLIC_DOMAIN`, any host in `PREVIEW_ALLOWED_HOSTS`, and Railway's healthcheck host.

## Supabase Auth settings (dashboard only)

1. Authentication, URL Configuration: Site URL `https://cba-copilot.up.railway.app`. Redirect URLs: add `https://cba-copilot.up.railway.app/**`.
2. Authentication, Providers, Email: turn off public signup (`disable_signup`).
3. Authentication, Emails, Templates: Magic Link must use the PKCE confirmation URL, for example `<p><a href="{{ .ConfirmationURL }}">Sign in to CBA Copilot</a></p>`. Do not put a raw `{{ .TokenHash }}` or `#access_token` link in the template.
4. Set OTP and magic-link expiry to 3600 seconds.
5. Optional: Authentication, Emails, SMTP Settings. Use a custom sender such as Resend. The default sender has a low hourly limit.
6. Optional heads-up mail on allow-list insert: store the mailer webhook URL as Vault secret `approval_mail_url`. The webhook must send the heads-up copy, never a login link. The key lives in Supabase Vault, not Railway `backend/.env`.

## Check a deploy

```bash
curl https://cba-copilot-api.up.railway.app/api/health   # {"ok":"true","mode":"live"}
curl -I https://cba-copilot-api.up.railway.app/docs       # 404 in production
curl -I https://cba-copilot.up.railway.app/               # CSP, HSTS, X-Frame-Options DENY
```

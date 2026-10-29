# Set up the frontend

From `frontend/`:

```bash
pnpm install
pnpm dev
pnpm lint
pnpm typecheck
pnpm build
```

The dev server proxies `/api` to `http://127.0.0.1:8000`. Start the backend first if you want the sample questions to answer.

pnpm is the only package manager. `.npmrc` refuses packages published in the last 7 days.

The button in `src/components/ui/button.tsx` is local. Add further primitives with `pnpm dlx shadcn@latest add <name>` rather than copying them by hand.

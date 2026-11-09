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

The screen uses Beautiful UI from <https://www.beautifului.dev/>. The registry is `@beautifului` in `components.json`. Installed source lives in `src/beautifui/foundation.css` and `src/components/beautifui/`. `shadow-plugin` supplies the foundation shadows. `class-variance-authority` supplies the button variants.

Add another primitive with `pnpm dlx shadcn@latest add https://www.beautifului.dev/r/<name>.json`. The CLI writes registry targets at the frontend root. Move those files into `src/` so the `@/` alias and `tsc` include them.

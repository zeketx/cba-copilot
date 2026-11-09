# Frontend

Read [../AGENTS.md](../AGENTS.md) first.

## Stack

Vite, React, TypeScript, Tailwind. pnpm only. No Next.js.

The glossary is `definitions/definitions.yaml`. Import it. Do not copy the entries into a second file.

Citation chips open the whole source in `FilingViewer`, scrolled to a span or element anchor with the passage highlighted and the surrounding sections still in the document. Definition links add `pdf_page_offset` from `data/corpus.json` to the printed page.

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm build
```

The UI is [Beautiful UI](https://www.beautifului.dev/), MIT. Source is in `src/components/beautifui/` and the theme is `src/beautifui/foundation.css`. Pass content through props. Theme through the foundation tokens (`--ink`, `--surface`, `--accent`) rather than one-off colors.

`shadow-plugin` is there because the foundation imports it. `class-variance-authority` is there because `Button` uses it. Add another primitive with `pnpm dlx shadcn@latest add https://www.beautifului.dev/r/<name>.json`, then move the CLI output into `src/` so the `@/` alias and `tsc` include it.

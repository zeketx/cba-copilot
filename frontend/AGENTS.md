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

Add shadcn primitives with the CLI when a screen needs one. The local `Button` is the only hand-written primitive.

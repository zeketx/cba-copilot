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

The UI is [Beautiful UI](https://www.beautifului.dev/), MIT. Source is in `src/components/beautifui/` (`Button`, `ContextCards`, `LoadingState`, `StreamText`, `ThinkingState`, `SidebarNav`, `GlideMenu`) and the theme is `src/beautifui/foundation.css` plus `src/beautifui/sidebar-nav.css`. Pass content through props. Theme through the foundation tokens (`--ink`, `--surface`, `--accent`) rather than one-off colors. Icons in vendored components are inline SVG because the registry's `@central-icons-react/round-outlined-radius-2-stroke-2` package is commercially licensed.

Chat states:

- Empty thread. Sample questions from `SAMPLE_QUESTIONS`.
- Thinking. `ThinkingState` until the first SSE `delta`.
- Streaming. Live delta text with the foundation caret. After `done` with no deltas, `StreamText` reveals the full reply. Do not use the Beautiful UI `StreamingText` gallery (follow-ups, demo sources, loop). `StreamText` is the primitive that fits this thread.
- Grounding refusal. `kind: "refusal"` on a saved assistant turn, red-tint card. Answer claim prose uses `react-markdown` (no raw HTML). Citation chips, claim cards, user bubbles, refusals, and clarifications stay plain text.
- Transport error. `chatRequestError` in `src/lib/request-error.ts`. A 502 is this banner plus retry, never the refusal card.

Leaving a thread (New chat, another thread, sign out) must abort the in-flight ask and drop `pending`/`revealing` so the next ask can POST.

`shadow-plugin` is there because the foundation imports it. `class-variance-authority` is there because `Button` uses it. Add another primitive with `pnpm dlx shadcn@latest add https://www.beautifului.dev/r/<name>.json`, then move the CLI output into `src/` so the `@/` alias and `tsc` include it.

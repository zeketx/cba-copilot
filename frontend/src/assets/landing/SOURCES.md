# Landing Page Assets — Sources & Licenses

## Monochrome Marble Cutouts

The decorative monochrome cutouts in this directory were **AI-generated** during T3 Code design sessions, knocked out from a pure white background to transparent WebP:

- `bust-cutout.webp` (341×480) — Isolated monochrome Greco-Roman marble bust cutout. AI-generated in T3 session.
- `bust-thinking-cutout.webp` (520×694) — AI-generated thinking-pose marble bust, hand to chin, transparent WebP. No logos or likenesses. Decorative.

These assets do not contain NBA or team logos, player likenesses, or third-party trademarks. They are decorative (`alt=""`, `aria-hidden="true"`).

## Self-Hosted Typography (`frontend/public/fonts/`)

All web fonts are self-hosted as Latin `.woff2` files so the production Content Security Policy (`font-src 'self'`) holds with zero external network calls:

- **Instrument Serif** (`instrument-serif-latin-normal.woff2`, `instrument-serif-latin-italic.woff2`) — SIL Open Font License 1.1 (OFL).
- **Instrument Sans** (`instrument-sans-latin-wght.woff2`) — SIL Open Font License 1.1 (OFL).
- **JetBrains Mono** (`jetbrains-mono-latin-wght.woff2`) — SIL Open Font License 1.1 (OFL).

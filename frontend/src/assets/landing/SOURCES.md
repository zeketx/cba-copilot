# Landing Page Assets — Sources & Licenses

## Monochrome Marble Cutouts

The decorative monochrome cutout in this directory was **AI-generated** during a T3 Code design session on this branch (`feat/landing-page-design`), knocked out from a pure white background to transparent WebP:

- `bust-cutout.webp` (341×480) — Isolated monochrome Greco-Roman marble bust cutout. AI-generated in T3 session.

This asset does not contain NBA or team logos, player likenesses, or third-party trademarks. It is decorative (`alt=""`, `aria-hidden="true"`).

## Self-Hosted Typography (`frontend/public/fonts/`)

All web fonts are self-hosted as Latin `.woff2` files so the production Content Security Policy (`font-src 'self'`) holds with zero external network calls:

- **Instrument Serif** (`instrument-serif-latin-normal.woff2`, `instrument-serif-latin-italic.woff2`) — SIL Open Font License 1.1 (OFL).
- **Instrument Sans** (`instrument-sans-latin-wght.woff2`) — SIL Open Font License 1.1 (OFL).
- **JetBrains Mono** (`jetbrains-mono-latin-wght.woff2`) — SIL Open Font License 1.1 (OFL).

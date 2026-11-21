# Landing Page Assets — Sources & Licenses

## Monochrome Marble Cutouts

The three decorative monochrome cutouts in this directory were **AI-generated** during a T3 Code design session on this branch (`feat/landing-page-design`), knocked out from pure white backgrounds to transparent WebP:

- `bust-cutout.webp` (341×480) — Isolated monochrome Greco-Roman marble bust cutout. AI-generated in T3 session.
- `hand-cutout.webp` (215×480) — Isolated monochrome classical marble sculptural hand cutout. AI-generated in T3 session.
- `sandal-cutout.webp` (440×312) — Isolated monochrome carved-marble Roman sandal / high-top silhouette with Greek key frieze and laurel detail (no shoe brand marks, no logos). AI-generated in T3 session.

None of these assets contain NBA or team logos, player likenesses, or third-party trademarks. They are decorative (`alt=""`, `aria-hidden="true"`).

## Self-Hosted Typography (`frontend/public/fonts/`)

All web fonts are self-hosted as Latin `.woff2` files so the production Content Security Policy (`font-src 'self'`) holds with zero external network calls:

- **Instrument Serif** (`instrument-serif-latin-normal.woff2`, `instrument-serif-latin-italic.woff2`) — SIL Open Font License 1.1 (OFL).
- **Instrument Sans** (`instrument-sans-latin-wght.woff2`) — SIL Open Font License 1.1 (OFL).
- **JetBrains Mono** (`jetbrains-mono-latin-wght.woff2`) — SIL Open Font License 1.1 (OFL).

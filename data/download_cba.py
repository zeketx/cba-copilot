
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

NBPA_PAGE = "https://nbpa.com/cba"
FALLBACK_PDF = (
    "https://imgix.cosmicjs.com/25da5eb0-15eb-11ee-b5b3-fbd321202bdf-"
    "Final-2023-NBA-Collective-Bargaining-Agreement-6-28-23.pdf"
)
DEST = Path(__file__).resolve().parent / "downloads" / "2023-nba-cba.pdf"
USER_AGENT = "cba-copilot-download/0.1"

def pdf_href_from_nbpa(html: str) -> str | None:
    match = re.search(
        r'href="(https://[^"]+2023[^"]+\.pdf)"',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None

def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()

def main() -> int:
    try:
        html = fetch(NBPA_PAGE).decode("utf-8", errors="replace")
        pdf_url = pdf_href_from_nbpa(html) or FALLBACK_PDF
    except OSError as exc:
        print(f"Could not read {NBPA_PAGE}: {exc}", file=sys.stderr)
        pdf_url = FALLBACK_PDF
    print(f"Downloading {pdf_url}")
    payload = fetch(pdf_url)
    if not payload.startswith(b"%PDF"):
        print("The download is not a PDF.", file=sys.stderr)
        return 1
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(payload)
    print(f"Wrote {DEST} ({len(payload)} bytes). It stays gitignored.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

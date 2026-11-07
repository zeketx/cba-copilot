
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

NBPA_PAGE = "https://nbpa.com/cba"
FALLBACK_PDF = (
    "https://imgix.cosmicjs.com/25da5eb0-15eb-11ee-b5b3-fbd321202bdf-"
    "Final-2023-NBA-Collective-Bargaining-Agreement-6-28-23.pdf"
)
DEST = Path(__file__).resolve().parent / "downloads" / "2023-nba-cba.pdf"
MANIFEST = DEST.parent / "manifest.json"
USER_AGENT = "cba-copilot-download/0.1"

_COVER_DATE = re.compile(r"JULY\s+2023", re.IGNORECASE)
_PRINTED_TERM = re.compile(
    r"This\s+Agreement\s+shall\s+be\s+effective\s+from"
    r".+?"
    r"June\s+30,\s+2030"
    r".+?"
    r"survive\s+expiration\s+or\s+termination\)\.",
    re.DOTALL,
)


@dataclass(frozen=True)
class CorpusManifest:
    url: str
    sha256: str
    cover_date: str
    printed_term: str


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def cover_date_from_text(text: str) -> str:
    if _COVER_DATE.search(text) is None:
        raise ValueError("cover date JULY 2023 is missing")
    return "July 2023"


def printed_term_from_text(text: str) -> str:
    match = _PRINTED_TERM.search(text)
    if match is None:
        raise ValueError("printed term sentence is missing")
    return " ".join(match.group(0).split())


def manifest_payload(url: str, pdf_bytes: bytes, text: str) -> CorpusManifest:
    return CorpusManifest(
        url=url,
        sha256=sha256_hex(pdf_bytes),
        cover_date=cover_date_from_text(text),
        printed_term=printed_term_from_text(text),
    )


def write_manifest(path: Path, manifest: CorpusManifest) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        json.dumps(
            {
                "url": manifest.url,
                "sha256": manifest.sha256,
                "cover_date": manifest.cover_date,
                "printed_term": manifest.printed_term,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".manifest.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def pdf_text(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        sys.exit(2)
    return completed.stdout.decode("utf-8", errors="replace")

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
    try:
        text = pdf_text(DEST)
        manifest = manifest_payload(pdf_url, payload, text)
    except subprocess.CalledProcessError as exc:
        print(f"pdftotext failed: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    write_manifest(MANIFEST, manifest)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

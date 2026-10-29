
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.request import Request, urlopen

RAW_ROOT = "https://raw.githubusercontent.com/atlhawksfanatic/NBA-CBA-2023/main"
TREE_API = "https://api.github.com/repos/atlhawksfanatic/NBA-CBA-2023/contents"
DEST = Path(__file__).resolve().parent / "markdown-aid"
USER_AGENT = "cba-copilot-download/0.1"

def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=60) as response:
        return response.read()

def main() -> int:
    parser = argparse.ArgumentParser(description="Download the unofficial article-split CBA markdown.")
    parser.add_argument(
        "--i-accept-the-unofficial-aid",
        action="store_true",
        help="Required. Confirms you have read the GPL-3.0 license and the accuracy disclaimer.",
    )
    args = parser.parse_args()
    if not args.i_accept_the_unofficial_aid:
        print(
            "Refusing to download. The aid repo is GPL-3.0 and the author disclaims accuracy. "
            "Pass --i-accept-the-unofficial-aid to write files under data/markdown-aid/.",
            file=sys.stderr,
        )
        return 2
    print("License: GPL-3.0. The files are an unofficial conversion. They are not committed.")
    listing = fetch(TREE_API)
    import json

    entries = json.loads(listing)
    names = [
        item["name"]
        for item in entries
        if item["name"].endswith((".Rmd", ".md")) and item["name"][:1].isdigit()
    ]
    DEST.mkdir(parents=True, exist_ok=True)
    for name in names:
        payload = fetch(f"{RAW_ROOT}/{name}")
        (DEST / name).write_bytes(payload)
        print(f"Wrote {name}")
    print(f"{len(names)} files in {DEST}. Map each chunk back to the official PDF before indexing.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

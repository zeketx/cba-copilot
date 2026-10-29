
from __future__ import annotations

import os
import re
import sys

_MODE_LINE = re.compile(r"^Mode:\s*(HARD|LIGHT)\b", re.MULTILINE)

def body_has_mode(body: str | None) -> bool:
    if not body:
        return False
    return _MODE_LINE.search(body) is not None

def main() -> int:
    body = os.environ.get("PR_BODY")
    if body_has_mode(body):
        print("Mode line found")
        return 0
    print("PR body needs a line that starts with `Mode: HARD` or `Mode: LIGHT`.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

DEFINITIONS_PATH = Path(__file__).resolve().parents[2] / "definitions" / "definitions.yaml"


@lru_cache
def load_definitions() -> dict[str, object]:
    loaded = yaml.safe_load(DEFINITIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("definitions file must be a mapping")
    return loaded

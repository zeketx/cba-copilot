import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "data" / "download_cba.py"
FIXTURE_BYTES = b"cba-fixture-pdf"
FIXTURE_SHA256 = "5f6885d318b43b6989c69384044e3da30054685cda4ad223e34228b701dc444d"
PRINTED_TERM = (
    "This Agreement shall be effective from July 1, 2023 (except with respect to "
    "provisions that the parties have specifically agreed herein will commence earlier) "
    "and, unless terminated pursuant to the provisions of this Article XXXIX, shall "
    "continue in full force and effect through June 30, 2030 (except with respect to "
    "provisions that the parties have specifically agreed herein will survive expiration "
    "or termination)."
)
FIXTURE_TEXT = """
COLLECTIVE BARGAINING AGREEMENT
JULY
2023
This Agreement shall be effective from July 1, 2023 (except with respect to
provisions that the parties have specifically agreed herein will commence earlier)
and, unless terminated pursuant to the provisions of this Article XXXIX, shall
continue in full force and effect through June 30, 2030 (except with respect to
provisions that the parties have specifically agreed herein will survive expiration
or termination).
"""


def load_download_cba():
    spec = importlib.util.spec_from_file_location("download_cba", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_records_hash_cover_date_and_printed_term() -> None:
    download = load_download_cba()
    manifest = download.manifest_payload(
        "https://example.test/cba.pdf",
        FIXTURE_BYTES,
        FIXTURE_TEXT,
    )
    assert manifest.url == "https://example.test/cba.pdf"
    assert manifest.sha256 == FIXTURE_SHA256
    assert download.sha256_hex(FIXTURE_BYTES) == FIXTURE_SHA256
    assert manifest.cover_date == "July 2023"
    assert manifest.printed_term == PRINTED_TERM


def test_cover_date_missing_raises() -> None:
    download = load_download_cba()
    with pytest.raises(ValueError):
        download.cover_date_from_text(PRINTED_TERM)


def test_write_manifest_is_stable(tmp_path: Path) -> None:
    download = load_download_cba()
    path = tmp_path / "manifest.json"
    manifest = download.manifest_payload(
        "https://example.test/cba.pdf",
        FIXTURE_BYTES,
        FIXTURE_TEXT,
    )
    download.write_manifest(path, manifest)
    first = path.read_bytes()
    download.write_manifest(path, manifest)
    second = path.read_bytes()
    assert first == second
    assert list(tmp_path.iterdir()) == [path]
    assert first.endswith(b"\n")

from pathlib import Path

import yaml
from app.api import create_app
from app.corpus import printed_page_to_pdf_page
from app.definitions import load_definitions
from evals.runner import main as run_eval
from evals.runner import run_suite
from fastapi.testclient import TestClient
from scripts.check_pr_mode import body_has_mode

ROOT = Path(__file__).resolve().parents[2]


def test_six_questions_pass_on_stand_in_models() -> None:
    assert run_suite() == []


def test_live_flag_exits_before_a_model_call() -> None:
    assert run_eval(["--live"]) == 2


def test_definitions_draft_has_verified_citations() -> None:
    document = load_definitions()
    assert document["status"] == "DRAFT"
    entries = document["entries"]
    assert isinstance(entries, list)
    assert len(entries) >= 30
    for entry in entries:
        assert entry["term"]
        assert entry["definition"]
        citation = entry["citation"]
        assert citation["article"]
        assert citation["section"]
        assert citation["page_start"] <= citation["page_end"]
        assert citation["verified"] is True
    text = (ROOT / "definitions" / "definitions.yaml").read_text(encoding="utf-8")
    assert text.startswith("# DRAFT")


def test_printed_page_offset_matches_the_july_2023_file() -> None:
    assert printed_page_to_pdf_page(1) == 25
    assert printed_page_to_pdf_page(190) == 214


def test_mode_line_check() -> None:
    assert body_has_mode("Mode: HARD\n\n## Why\n")
    assert body_has_mode("Hello\nMode: LIGHT\n")
    assert not body_has_mode("Mode: MEDIUM\n")
    assert not body_has_mode("")
    assert not body_has_mode(None)


def test_migration_creates_vector_and_full_text_indexes() -> None:
    migration = (
        ROOT / "backend" / "alembic" / "versions" / "c0a2023b0001_cba_schema.py"
    ).read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "search_vector tsvector" in migration
    assert "to_tsvector" in migration
    assert "USING gin (search_vector)" in migration
    assert "USING hnsw (embedding vector_cosine_ops)" in migration


def test_ask_endpoint_answers_and_refuses() -> None:
    client = TestClient(create_app())
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "fake"

    answer = client.post(
        "/api/ask",
        json={"question": "What can't a second-apron team do in a trade?"},
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["kind"] == "answer"
    citation = body["claims"][0]["citations"][0]
    assert citation["source_url"].endswith("#page=214")
    assert citation["placement"]["kind"] == "span"
    assert citation["source_html"].count("<section>") > 1
    assert citation["placement"]["start_id"] in citation["source_html"]

    refusal = client.post(
        "/api/ask",
        json={"question": "How many timeouts may an NHL coach call during a playoff overtime?"},
    )
    assert refusal.status_code == 200
    assert refusal.json()["kind"] == "refusal"

    definitions = client.get("/api/definitions")
    assert definitions.status_code == 200
    loaded = yaml.safe_load((ROOT / "definitions" / "definitions.yaml").read_text(encoding="utf-8"))
    assert definitions.json()["status"] == loaded["status"]

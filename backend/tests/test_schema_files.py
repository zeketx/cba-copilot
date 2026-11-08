from pathlib import Path

from app.database.models import CbaChunk

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "backend" / "alembic" / "versions" / "c0a2023b0002_chunk_pages_and_rls.py"
)


def test_chunk_model_has_separate_page_and_quote_fields() -> None:
    columns = CbaChunk.__table__.c
    for name in ("printed_page", "viewer_page", "quote_start", "quote_end"):
        assert columns[name].nullable is True


def test_second_migration_adds_pages_gin_and_default_deny() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "c0a2023b0001"' in text
    for column in ("printed_page", "viewer_page", "quote_start", "quote_end"):
        assert f'"{column}"' in text
    assert "USING gin (chunk_metadata)" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "REVOKE ALL ON TABLE" in text
    assert "rolname = 'anon'" in text
    assert "rolname = 'authenticated'" in text
    assert "CREATE POLICY" not in text
    downgrade = text.split("def downgrade", 1)[1]
    assert "rolname = 'anon'" in downgrade
    assert "rolname = 'authenticated'" in downgrade
    assert downgrade.index("rolname = 'anon'") < downgrade.index("GRANT ALL ON TABLE")
    assert "chat_threads" not in text

from pathlib import Path

SQL = Path(__file__).resolve().parents[1] / "scripts" / "app_role.sql"

CORPUS_TABLES = ("source_documents", "cba_chunks")
CHAT_TABLES = (
    "users",
    "chat_threads",
    "chat_messages",
    "message_citations",
    "access_requests",
)


def _sql() -> str:
    return SQL.read_text(encoding="utf-8")


def test_app_role_sql_creates_one_login_role() -> None:
    text = _sql()
    assert text.count("CREATE ROLE cba_copilot_app") == 1
    assert "LOGIN" in text
    assert "NOSUPERUSER" in text
    assert "service_role" not in text
    assert "SUPERUSER" not in text.replace("NOSUPERUSER", "")


def test_app_role_sql_grants_corpus_select() -> None:
    text = _sql()
    select_grant = text.split("GRANT SELECT ON TABLE", 1)[1].split("GRANT", 1)[0]
    for table in CORPUS_TABLES:
        assert table in select_grant
    for table in CHAT_TABLES:
        assert table not in select_grant


def test_app_role_sql_grants_chat_read_write() -> None:
    text = _sql()
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE" in text
    write_grant = text.split("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE", 1)[1]
    for table in CHAT_TABLES:
        assert table in write_grant
    for table in CORPUS_TABLES:
        assert table not in write_grant


def test_app_role_sql_has_no_row_policy() -> None:
    text = _sql().lower()
    assert "create policy" not in text
    assert "alembic_version" not in text

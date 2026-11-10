from pathlib import Path

from app.database.models import (
    Base,
    CbaChunk,
    ChatMessage,
    ChatThread,
    MessageCitation,
    User,
)
from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "backend" / "alembic" / "versions" / "c0a2023b0002_chunk_pages_and_rls.py"
)
CHAT_MIGRATION = ROOT / "backend" / "alembic" / "versions" / "c0a2023b0003_chat_tables.py"
ENV_PY = ROOT / "backend" / "alembic" / "env.py"


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


def test_chat_migration_adds_tables_default_deny_and_auth_fk() -> None:
    text = CHAT_MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "c0a2023b0002"' in text
    for name in ("users", "chat_threads", "chat_messages", "message_citations"):
        assert name in text
    assert "fk_users_id_auth_users" in text
    assert "REFERENCES auth.users" in text
    assert "cba_chunks" in text
    assert "document_chunks" not in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "REVOKE ALL" in text
    assert "CREATE POLICY" not in text
    for banned in ("company", "filing_date", "filing"):
        assert banned not in text
    assert "rolname = 'anon'" in text
    assert "rolname = 'authenticated'" in text
    downgrade = text.split("def downgrade", 1)[1]
    assert "DROP POLICY" not in downgrade
    assert downgrade.index("rolname = 'anon'") < downgrade.index("GRANT ALL ON TABLE")
    assert downgrade.index("GRANT ALL ON TABLE") < downgrade.index("DISABLE ROW LEVEL SECURITY")
    assert downgrade.index("DISABLE ROW LEVEL SECURITY") < downgrade.index(
        "DROP CONSTRAINT fk_users_id_auth_users"
    )
    drop_citations = downgrade.index('op.drop_table("message_citations")')
    drop_messages = downgrade.index('op.drop_table("chat_messages")')
    drop_threads = downgrade.index('op.drop_table("chat_threads")')
    drop_users = downgrade.index('op.drop_table("users")')
    assert downgrade.index("DROP CONSTRAINT fk_users_id_auth_users") < drop_citations
    assert drop_citations < drop_messages < drop_threads < drop_users


def test_chat_models_expose_locked_columns() -> None:
    assert {"users", "chat_threads", "chat_messages", "message_citations"} <= set(
        Base.metadata.tables
    )
    assert list(User.__table__.foreign_keys) == []
    assert User.__table__.c.id.primary_key
    assert User.__table__.c.id.server_default is None
    assert {column.name for column in User.__table__.columns} == {"id"}

    thread = ChatThread.__table__
    assert {column.name for column in thread.columns} == {
        "id",
        "user_id",
        "title",
        "created_at",
        "updated_at",
    }
    assert thread.c.user_id.nullable is False
    assert thread.c.title.nullable is False
    assert "gen_random_uuid" in str(thread.c.id.server_default.arg)
    user_fk = next(iter(thread.c.user_id.foreign_keys))
    assert user_fk.column.table.name == "users"
    assert user_fk.ondelete == "CASCADE"
    assert "ix_chat_threads_user_id" in {index.name for index in thread.indexes}

    message = ChatMessage.__table__
    assert {column.name for column in message.columns} == {
        "id",
        "thread_id",
        "role",
        "position",
        "message",
        "usage",
        "created_at",
    }
    assert isinstance(message.c.role.type, String)
    assert message.c.role.type.length == 16
    assert message.c.role.nullable is False
    assert message.c.position.nullable is False
    assert isinstance(message.c.message.type, JSONB)
    assert message.c.message.nullable is False
    assert isinstance(message.c.usage.type, JSONB)
    assert message.c.usage.nullable is True
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in message.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "user" in checks["role"] and "assistant" in checks["role"]
    assert "usage IS NULL" in checks["usage_assistant"]
    uniques = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in message.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert uniques["uq_chat_messages_thread_id"] == ("thread_id", "position")
    thread_fk = next(iter(message.c.thread_id.foreign_keys))
    assert thread_fk.column.table.name == "chat_threads"
    assert thread_fk.ondelete == "CASCADE"

    citation = MessageCitation.__table__
    assert {column.name for column in citation.columns} == {
        "id",
        "message_id",
        "chunk_id",
        "sort_index",
    }
    chunk_fk = next(iter(citation.c.chunk_id.foreign_keys))
    assert chunk_fk.column.table.name == "cba_chunks"
    assert chunk_fk.column.name == "id"
    assert chunk_fk.ondelete == "RESTRICT"
    message_fk = next(iter(citation.c.message_id.foreign_keys))
    assert message_fk.ondelete == "CASCADE"
    cite_uniques = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in citation.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert cite_uniques["uq_message_citations_message_id"] == ("message_id", "sort_index")
    assert "ix_message_citations_message_id" in {index.name for index in citation.indexes}
    assert "ix_message_citations_chunk_id" in {index.name for index in citation.indexes}


def test_env_registers_chat_models() -> None:
    text = ENV_PY.read_text(encoding="utf-8")
    for name in ("User", "ChatThread", "ChatMessage", "MessageCitation"):
        assert f"{name}.__tablename__" in text
    assert "RuntimeError" in text

"""chat row policies

Revision ID: c0a2023b0008
Revises: c0a2023b0007
Create Date: 2026-11-14

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c0a2023b0008"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USERS = "id = auth.uid()"
_THREADS = "user_id = auth.uid()"
_MESSAGES = (
    "EXISTS (SELECT 1 FROM chat_threads "
    "WHERE chat_threads.id = chat_messages.thread_id "
    "AND chat_threads.user_id = auth.uid())"
)
_CITATIONS = (
    "EXISTS (SELECT 1 FROM chat_messages "
    "JOIN chat_threads ON chat_threads.id = chat_messages.thread_id "
    "WHERE chat_messages.id = message_citations.message_id "
    "AND chat_threads.user_id = auth.uid())"
)

# No TO clause: the policy applies to every non-bypass role.
POLICIES: tuple[tuple[str, str, str, str], ...] = (
    ("users", "users_owner", _USERS, _USERS),
    ("chat_threads", "chat_threads_owner", _THREADS, _THREADS),
    ("chat_messages", "chat_messages_owner", _MESSAGES, _MESSAGES),
    ("message_citations", "message_citations_owner", _CITATIONS, _CITATIONS),
)


def upgrade() -> None:
    for table, name, using_sql, check_sql in POLICIES:
        op.execute(
            f"""
            CREATE POLICY {name} ON {table}
              USING ({using_sql})
              WITH CHECK ({check_sql})
            """
        )


def downgrade() -> None:
    for table, name, _using_sql, _check_sql in reversed(POLICIES):
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")

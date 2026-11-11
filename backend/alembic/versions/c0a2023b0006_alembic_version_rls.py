"""default-deny RLS on alembic_version

Revision ID: c0a2023b0006
Revises: c0a2023b0005
Create Date: 2026-11-10

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c0a2023b0006"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "alembic_version"
ROLES = ("anon", "authenticated")


def _for_api_roles(statement: str) -> None:
    for role in ROLES:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{statement.format(role=role)}';
              END IF;
            END
            $$
            """
        )


def upgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    _for_api_roles(f"REVOKE ALL ON TABLE {TABLE} FROM {{role}}")


def downgrade() -> None:
    _for_api_roles(f"GRANT ALL ON TABLE {TABLE} TO {{role}}")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY")

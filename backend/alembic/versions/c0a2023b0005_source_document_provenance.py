"""source document provenance

Revision ID: c0a2023b0005
Revises: c0a2023b0004
Create Date: 2026-11-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0a2023b0005"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "source_documents"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("sha256", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("cover_date", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("printed_term", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("page_offset", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("text", sa.Text(), nullable=True))
    op.add_column(
        TABLE,
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_source_documents_source_url", TABLE, ["source_url"])


def downgrade() -> None:
    op.drop_constraint("uq_source_documents_source_url", TABLE, type_="unique")
    op.drop_column(TABLE, "updated_at")
    op.drop_column(TABLE, "text")
    op.drop_column(TABLE, "page_offset")
    op.drop_column(TABLE, "printed_term")
    op.drop_column(TABLE, "cover_date")
    op.drop_column(TABLE, "sha256")

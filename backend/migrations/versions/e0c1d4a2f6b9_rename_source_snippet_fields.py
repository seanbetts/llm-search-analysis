"""Rename response_sources snippet field and drop query_sources snippet field.

- Drop `query_sources.snippet_text` (unused/redundant).
- Rename `response_sources.snippet_text` -> `response_sources.search_description`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0c1d4a2f6b9"
down_revision: Union[str, None] = "d4b4c7d05b3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  with op.batch_alter_table("query_sources") as batch:
    batch.drop_column("snippet_text")

  with op.batch_alter_table("response_sources") as batch:
    batch.alter_column("snippet_text", new_column_name="search_description")


def downgrade() -> None:
  with op.batch_alter_table("response_sources") as batch:
    batch.alter_column("search_description", new_column_name="snippet_text")

  with op.batch_alter_table("query_sources") as batch:
    batch.add_column(sa.Column("snippet_text", sa.Text(), nullable=True))

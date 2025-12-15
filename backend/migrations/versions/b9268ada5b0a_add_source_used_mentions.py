"""Add citation mention table for sources_used.

Revision ID: b9268ada5b0a
Revises: 4a1d8d29f1b4
Create Date: 2025-12-15 14:14:41.851954

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b9268ada5b0a'
down_revision: Union[str, None] = '4a1d8d29f1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "source_used_mentions",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("source_used_id", sa.Integer(), nullable=False),
    sa.Column("response_id", sa.Integer(), nullable=False),
    sa.Column("mention_index", sa.Integer(), nullable=False),
    sa.Column("start_index", sa.Integer(), nullable=True),
    sa.Column("end_index", sa.Integer(), nullable=True),
    sa.Column("snippet_cited", sa.Text(), nullable=True),
    sa.Column("metadata_json", sa.JSON(), nullable=True),
    sa.Column("function_tags", sa.JSON(), nullable=False),
    sa.Column("stance_tags", sa.JSON(), nullable=False),
    sa.Column("provenance_tags", sa.JSON(), nullable=False),
    sa.Column("influence_summary", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(["response_id"], ["responses.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["source_used_id"], ["sources_used.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
  )

  with op.batch_alter_table("source_used_mentions") as batch:
    batch.create_index("ix_source_used_mentions_created_at", ["created_at"], unique=False)
    batch.create_index("ix_source_used_mentions_response_id", ["response_id"], unique=False)
    batch.create_index("ix_source_used_mentions_source_used_id", ["source_used_id"], unique=False)
    batch.create_index(
      "ix_source_used_mentions_source_used_id_mention_index",
      ["source_used_id", "mention_index"],
      unique=True,
    )


def downgrade() -> None:
  with op.batch_alter_table("source_used_mentions") as batch:
    batch.drop_index("ix_source_used_mentions_source_used_id_mention_index")
    batch.drop_index("ix_source_used_mentions_source_used_id")
    batch.drop_index("ix_source_used_mentions_response_id")
    batch.drop_index("ix_source_used_mentions_created_at")
  op.drop_table("source_used_mentions")

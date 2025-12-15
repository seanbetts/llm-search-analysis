"""Add citation tagging status columns to responses.

This revision also resolves the previous multi-head migration state by merging
the existing heads into a single lineage.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0b3b0f63b0c1"
down_revision: Union[str, Sequence[str], None] = ("c7b2efb7c651", "e0c1d4a2f6b9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  with op.batch_alter_table("responses") as batch:
    batch.add_column(sa.Column("citation_tagging_status", sa.String(length=32), nullable=True))
    batch.add_column(sa.Column("citation_tagging_error", sa.Text(), nullable=True))
    batch.add_column(sa.Column("citation_tagging_started_at", sa.DateTime(), nullable=True))
    batch.add_column(sa.Column("citation_tagging_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
  with op.batch_alter_table("responses") as batch:
    batch.drop_column("citation_tagging_completed_at")
    batch.drop_column("citation_tagging_started_at")
    batch.drop_column("citation_tagging_error")
    batch.drop_column("citation_tagging_status")


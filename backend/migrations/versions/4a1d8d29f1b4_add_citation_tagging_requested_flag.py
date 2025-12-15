"""Add citation_tagging_requested flag to responses.

This captures per-interaction user intent (e.g., toggled in the UI) to run
citation tagging for web captures without relying on global env flags.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a1d8d29f1b4"
down_revision: Union[str, None] = "0b3b0f63b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  with op.batch_alter_table("responses") as batch:
    batch.add_column(sa.Column("citation_tagging_requested", sa.Boolean(), nullable=False, server_default=sa.true()))

  with op.batch_alter_table("responses") as batch:
    batch.alter_column("citation_tagging_requested", server_default=None)


def downgrade() -> None:
  with op.batch_alter_table("responses") as batch:
    batch.drop_column("citation_tagging_requested")


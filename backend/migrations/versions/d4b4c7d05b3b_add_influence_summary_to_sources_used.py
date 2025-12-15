"""Add influence_summary column to sources_used."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b4c7d05b3b"
down_revision: Union[str, None] = "7f7bfbd8e7b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  with op.batch_alter_table("sources_used") as batch:
    batch.add_column(sa.Column("influence_summary", sa.Text(), nullable=True))


def downgrade() -> None:
  with op.batch_alter_table("sources_used") as batch:
    batch.drop_column("influence_summary")

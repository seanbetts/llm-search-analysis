"""Rename sources_used.snippet_used to snippet_cited."""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7f7bfbd8e7b6"
down_revision = "c7b2efb7c651"
branch_labels = None
depends_on = None


def upgrade():
  with op.batch_alter_table("sources_used") as batch_op:
    batch_op.alter_column("snippet_used", new_column_name="snippet_cited")


def downgrade():
  with op.batch_alter_table("sources_used") as batch_op:
    batch_op.alter_column("snippet_cited", new_column_name="snippet_used")

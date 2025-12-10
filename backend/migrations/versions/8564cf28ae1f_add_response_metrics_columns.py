"""add response metrics columns

Revision ID: 8564cf28ae1f
Revises: 1faa14f77fa5
Create Date: 2025-12-07 22:06:14.417908

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '8564cf28ae1f'
down_revision: Union[str, None] = '1faa14f77fa5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("responses")}

    add_sources_found = "sources_found" not in columns
    add_sources_used = "sources_used_count" not in columns
    add_avg_rank = "avg_rank" not in columns

    if add_sources_found or add_sources_used or add_avg_rank:
        with op.batch_alter_table('responses', schema=None) as batch:
            if add_sources_found:
                batch.add_column(sa.Column('sources_found', sa.Integer(), nullable=False, server_default='0'))
            if add_sources_used:
                batch.add_column(sa.Column('sources_used_count', sa.Integer(), nullable=False, server_default='0'))
            if add_avg_rank:
                batch.add_column(sa.Column('avg_rank', sa.Float(), nullable=True))

    if add_sources_found or add_sources_used:
        with op.batch_alter_table('responses', schema=None) as batch:
            if add_sources_found:
                batch.alter_column('sources_found', server_default=None)
            if add_sources_used:
                batch.alter_column('sources_used_count', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("responses")}

    drop_columns = any(
        name in columns
        for name in ("avg_rank", "sources_used_count", "sources_found")
    )
    if not drop_columns:
        return

    with op.batch_alter_table('responses', schema=None) as batch:
        if "avg_rank" in columns:
            batch.drop_column('avg_rank')
        if "sources_used_count" in columns:
            batch.drop_column('sources_used_count')
        if "sources_found" in columns:
            batch.drop_column('sources_found')

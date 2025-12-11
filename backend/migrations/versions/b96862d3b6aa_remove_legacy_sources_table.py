"""remove legacy sources table if it still exists

Revision ID: b96862d3b6aa
Revises: 9b9f1c6a2e3f
Create Date: 2025-12-09 16:37:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'b96862d3b6aa'
down_revision: Union[str, None] = '9b9f1c6a2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'sources' in inspector.get_table_names():
        op.drop_table('sources')


def downgrade() -> None:
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('search_query_id', sa.Integer(), nullable=True),
        sa.Column('response_id', sa.Integer(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('pub_date', sa.String(length=50), nullable=True),
        sa.Column('snippet_text', sa.Text(), nullable=True),
        sa.Column('internal_score', sa.Float(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['search_query_id'], ['search_queries.id']),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sources_search_query_id', 'sources', ['search_query_id'], unique=False)
    op.create_index('ix_sources_response_id', 'sources', ['response_id'], unique=False)

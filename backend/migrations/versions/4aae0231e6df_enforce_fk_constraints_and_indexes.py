"""enforce fk constraints and indexes

Revision ID: 4aae0231e6df
Revises: 1058847fd4ba
Create Date: 2025-12-07 15:53:22.773867

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4aae0231e6df'
down_revision: Union[str, None] = '1058847fd4ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop unused legacy tables if they still exist
    op.execute(sa.text("DROP TABLE IF EXISTS search_calls"))
    op.execute(sa.text("DROP TABLE IF EXISTS citations"))

    # Enforce non-null foreign keys
    with op.batch_alter_table('sessions') as batch:
        batch.alter_column('provider_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('prompts') as batch:
        batch.alter_column('session_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('responses') as batch:
        batch.alter_column('prompt_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('search_queries') as batch:
        batch.alter_column('response_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('sources_used') as batch:
        batch.alter_column('response_id', existing_type=sa.Integer(), nullable=False)

    # Add high-value indexes
    op.create_index('ix_responses_created_at', 'responses', ['created_at'], unique=False)
    op.create_index('ix_search_queries_response_id', 'search_queries', ['response_id'], unique=False)
    op.create_index('ix_sources_response_id', 'sources', ['response_id'], unique=False)
    op.create_index('ix_sources_search_query_id', 'sources', ['search_query_id'], unique=False)
    op.create_index('ix_sources_used_response_id', 'sources_used', ['response_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_sources_used_response_id', table_name='sources_used')
    op.drop_index('ix_sources_search_query_id', table_name='sources')
    op.drop_index('ix_sources_response_id', table_name='sources')
    op.drop_index('ix_search_queries_response_id', table_name='search_queries')
    op.drop_index('ix_responses_created_at', table_name='responses')

    with op.batch_alter_table('sources_used') as batch:
        batch.alter_column('response_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('search_queries') as batch:
        batch.alter_column('response_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('responses') as batch:
        batch.alter_column('prompt_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('prompts') as batch:
        batch.alter_column('session_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('sessions') as batch:
        batch.alter_column('provider_id', existing_type=sa.Integer(), nullable=True)

    op.create_table(
        'search_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.Integer(), nullable=True),
        sa.Column('search_query', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'citations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.Integer(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id']),
        sa.PrimaryKeyConstraint('id'),
    )

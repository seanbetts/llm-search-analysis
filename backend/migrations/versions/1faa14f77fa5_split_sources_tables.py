"""split sources tables

Revision ID: 1faa14f77fa5
Revises: 4aae0231e6df
Create Date: 2025-12-07 16:02:53.753038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1faa14f77fa5'
down_revision: Union[str, None] = '4aae0231e6df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new normalized source tables
    op.create_table(
        'response_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('pub_date', sa.String(length=50), nullable=True),
        sa.Column('snippet_text', sa.Text(), nullable=True),
        sa.Column('internal_score', sa.Float(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_response_sources_response_id', 'response_sources', ['response_id'], unique=False)

    op.create_table(
        'query_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('search_query_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('pub_date', sa.String(length=50), nullable=True),
        sa.Column('snippet_text', sa.Text(), nullable=True),
        sa.Column('internal_score', sa.Float(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['search_query_id'], ['search_queries.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_query_sources_search_query_id', 'query_sources', ['search_query_id'], unique=False)

    # Add linkage columns for citations
    with op.batch_alter_table('sources_used') as batch:
        batch.add_column(sa.Column('query_source_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('response_source_id', sa.Integer(), nullable=True))
        batch.create_index('ix_sources_used_query_source_id', ['query_source_id'])
        batch.create_index('ix_sources_used_response_source_id', ['response_source_id'])
        batch.create_foreign_key(
            'fk_sources_used_query_source',
            'query_sources',
            ['query_source_id'],
            ['id'],
        )
        batch.create_foreign_key(
            'fk_sources_used_response_source',
            'response_sources',
            ['response_source_id'],
            ['id'],
        )
        batch.create_check_constraint(
            'ck_sources_used_single_reference',
            '(query_source_id IS NULL) OR (response_source_id IS NULL)',
        )

    conn = op.get_bind()

    # Copy existing data into the new tables, preserving IDs
    conn.execute(sa.text("""
        INSERT INTO query_sources (
            id, search_query_id, url, title, domain, rank, pub_date,
            snippet_text, internal_score, metadata_json
        )
        SELECT
            id, search_query_id, url, title, domain, rank, pub_date,
            snippet_text, internal_score, metadata_json
        FROM sources
        WHERE search_query_id IS NOT NULL
    """))

    conn.execute(sa.text("""
        INSERT INTO response_sources (
            id, response_id, url, title, domain, rank, pub_date,
            snippet_text, internal_score, metadata_json
        )
        SELECT
            id, response_id, url, title, domain, rank, pub_date,
            snippet_text, internal_score, metadata_json
        FROM sources
        WHERE search_query_id IS NULL
    """))

    # Link citations to their corresponding sources using URL (and implicitly rank/order)
    conn.execute(sa.text("""
        UPDATE sources_used
        SET query_source_id = (
            SELECT s.id FROM sources s
            WHERE s.search_query_id IS NOT NULL
              AND s.url = sources_used.url
            ORDER BY COALESCE(s.rank, 10e6), s.id
            LIMIT 1
        )
        WHERE query_source_id IS NULL
    """))

    conn.execute(sa.text("""
        UPDATE sources_used
        SET response_source_id = (
            SELECT s.id FROM sources s
            WHERE s.search_query_id IS NULL
              AND s.response_id = sources_used.response_id
              AND s.url = sources_used.url
            ORDER BY COALESCE(s.rank, 10e6), s.id
            LIMIT 1
        )
        WHERE response_source_id IS NULL
          AND query_source_id IS NULL
    """))

    # Drop the legacy sources table now that data has been migrated
    op.drop_table('sources')


def downgrade() -> None:
    # Recreate the original sources table
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
        sa.ForeignKeyConstraint(['response_id'], ['responses.id']),
        sa.ForeignKeyConstraint(['search_query_id'], ['search_queries.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sources_search_query_id', 'sources', ['search_query_id'], unique=False)
    op.create_index('ix_sources_response_id', 'sources', ['response_id'], unique=False)

    conn = op.get_bind()
    # Copy data back into the legacy table
    conn.execute(sa.text("""
        INSERT INTO sources (
            id, search_query_id, response_id, url, title, domain, rank,
            pub_date, snippet_text, internal_score, metadata_json
        )
        SELECT
            id, search_query_id, NULL, url, title, domain, rank,
            pub_date, snippet_text, internal_score, metadata_json
        FROM query_sources
    """))

    conn.execute(sa.text("""
        INSERT INTO sources (
            id, search_query_id, response_id, url, title, domain, rank,
            pub_date, snippet_text, internal_score, metadata_json
        )
        SELECT
            id, NULL, response_id, url, title, domain, rank,
            pub_date, snippet_text, internal_score, metadata_json
        FROM response_sources
    """))

    # Remove new foreign keys/columns from sources_used
    with op.batch_alter_table('sources_used') as batch:
        batch.drop_constraint('ck_sources_used_single_reference', type_='check')
        batch.drop_constraint('fk_sources_used_response_source', type_='foreignkey')
        batch.drop_constraint('fk_sources_used_query_source', type_='foreignkey')
        batch.drop_index('ix_sources_used_response_source_id')
        batch.drop_index('ix_sources_used_query_source_id')
        batch.drop_column('response_source_id')
        batch.drop_column('query_source_id')

    # Drop the normalized tables
    op.drop_index('ix_query_sources_search_query_id', table_name='query_sources')
    op.drop_table('query_sources')
    op.drop_index('ix_response_sources_response_id', table_name='response_sources')
    op.drop_table('response_sources')

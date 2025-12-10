"""add interactions table and drop sessions/prompts

Revision ID: 9b9f1c6a2e3f
Revises: 1faa14f77fa5
Create Date: 2025-12-07 21:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9b9f1c6a2e3f'
down_revision: Union[str, None] = '8564cf28ae1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('data_source', sa.String(length=20), nullable=False, server_default='api'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interactions_created_at', 'interactions', ['created_at'], unique=False)
    op.create_index('ix_interactions_provider_id', 'interactions', ['provider_id'], unique=False)
    op.create_index('ix_interactions_data_source', 'interactions', ['data_source'], unique=False)

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.add_column(sa.Column('interaction_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.create_foreign_key(
            'fk_responses_interactions',
            'interactions',
            ['interaction_id'],
            ['id'],
            ondelete='CASCADE',
        )

    conn = op.get_bind()

    # Backfill interactions from existing prompts/sessions
    conn.execute(sa.text("""
        INSERT INTO interactions (id, provider_id, model_name, prompt_text, data_source, created_at, updated_at)
        SELECT
            p.id,
            s.provider_id,
            COALESCE(s.model_used, ''),
            p.prompt_text,
            COALESCE(r.data_source, 'api'),
            COALESCE(p.created_at, r.created_at),
            COALESCE(p.created_at, r.created_at)
        FROM prompts p
        JOIN sessions s ON p.session_id = s.id
        JOIN responses r ON r.prompt_id = p.id
    """))

    conn.execute(sa.text("UPDATE responses SET interaction_id = prompt_id"))

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.alter_column('interaction_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.drop_column('prompt_id')

    op.drop_table('prompts')
    op.drop_table('sessions')


def downgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO sessions (id, provider_id, model_used, created_at)
        SELECT id, provider_id, model_name, created_at
        FROM interactions
    """))
    conn.execute(sa.text("""
        INSERT INTO prompts (id, session_id, prompt_text, created_at)
        SELECT id, id, prompt_text, created_at
        FROM interactions
    """))

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.add_column(sa.Column('prompt_id', sa.Integer(), nullable=True))

    conn.execute(sa.text("UPDATE responses SET prompt_id = interaction_id"))

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.create_foreign_key(
            'fk_responses_prompts',
            'prompts',
            ['prompt_id'],
            ['id'],
        )

    with op.batch_alter_table('responses', schema=None) as batch:
        batch.drop_constraint('fk_responses_interactions', type_='foreignkey')
        batch.drop_column('interaction_id')

    op.drop_index('ix_interactions_data_source', table_name='interactions')
    op.drop_index('ix_interactions_provider_id', table_name='interactions')
    op.drop_index('ix_interactions_created_at', table_name='interactions')
    op.drop_table('interactions')

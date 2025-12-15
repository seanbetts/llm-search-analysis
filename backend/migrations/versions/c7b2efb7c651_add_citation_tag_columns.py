"""add citation tagging columns to sources_used

Revision ID: c7b2efb7c651
Revises: b96862d3b6aa
Create Date: 2025-12-11 17:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7b2efb7c651'
down_revision: Union[str, None] = 'b96862d3b6aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sources_used') as batch:
        batch.add_column(sa.Column('function_tags', sa.JSON(), nullable=False, server_default='[]'))
        batch.add_column(sa.Column('stance_tags', sa.JSON(), nullable=False, server_default='[]'))
        batch.add_column(sa.Column('provenance_tags', sa.JSON(), nullable=False, server_default='[]'))

    with op.batch_alter_table('sources_used') as batch:
        batch.alter_column('function_tags', server_default=None)
        batch.alter_column('stance_tags', server_default=None)
        batch.alter_column('provenance_tags', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('sources_used') as batch:
        batch.drop_column('provenance_tags')
        batch.drop_column('stance_tags')
        batch.drop_column('function_tags')

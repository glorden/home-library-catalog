"""extraction call log

Revision ID: d2016aa38b56
Revises: bcec5f97babf
Create Date: 2026-07-26 10:44:23.904444

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = 'd2016aa38b56'
down_revision: str | None = 'bcec5f97babf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('extraction_calls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
    sa.Column('model_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('image_count', sa.Integer(), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('tokens_input', sa.Integer(), nullable=True),
    sa.Column('tokens_output', sa.Integer(), nullable=True),
    sa.Column('error_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('extraction_calls')

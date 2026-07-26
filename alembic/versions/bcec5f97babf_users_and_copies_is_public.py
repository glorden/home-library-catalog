"""users and copies is_public

Revision ID: bcec5f97babf
Revises: 221df1dc2393
Create Date: 2026-07-26 10:43:25.555347

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = 'bcec5f97babf'
down_revision: str | None = '221df1dc2393'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('password_hash', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('session_version', sa.Integer(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    # server_default нужен, потому что copies — существующая таблица, в
    # которой уже могут быть строки (в отличие от новой users выше);
    # opt-out модель видимости — существующие экземпляры остаются публичными.
    op.add_column('copies', sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column('copies', 'is_public')
    op.drop_table('users')

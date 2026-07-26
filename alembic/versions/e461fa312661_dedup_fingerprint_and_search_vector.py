"""dedup fingerprint and search vector

Revision ID: e461fa312661
Revises: d2016aa38b56
Create Date: 2026-07-26 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.dedup import compute_fingerprint

revision: str = 'e461fa312661'
down_revision: str | None = 'd2016aa38b56'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Тот же текст, что и SEARCH_VECTOR_SQL в app/models/edition.py — совпадение
# осознанное: миграции статичны и не импортируют модель, чтобы не менять
# задним числом уже применённую историю схемы, если модель когда-нибудь
# изменится.
SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(authors, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(subtitle, '')), 'B') || "
    "setweight(to_tsvector('russian', coalesce(original_title, '')), 'B') || "
    "setweight(to_tsvector('russian', coalesce(series, '')), 'B') || "
    "setweight(to_tsvector('russian', coalesce(publisher, '')), 'C') || "
    "setweight(to_tsvector('russian', coalesce(description, '')), 'D')"
)


def upgrade() -> None:
    op.add_column(
        'editions',
        sa.Column('dedup_fingerprint', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    )
    op.create_index('ix_editions_dedup_fingerprint', 'editions', ['dedup_fingerprint'], unique=False)

    # Бэкофилл существующих строк (сегодня их 0, но код должен быть верным и
    # для БД, где они уже есть). compute_fingerprint — чистая функция без
    # завязки на схему, импортируется из живого app.services.dedup (миграции
    # в этом проекте и так не изолированы от кода приложения — alembic/env.py
    # уже делает `from app import models` безусловно). Доступ к строкам — не
    # через ORM-класс Edition, а через узкий sa.table()-прокси на нужные
    # колонки, чтобы не завязываться на БУДУЩУЮ форму таблицы, если эта
    # миграция когда-нибудь реплеится после более поздних миграций.
    editions_t = sa.table(
        'editions',
        sa.column('id', sa.Integer),
        sa.column('title', sa.String),
        sa.column('authors', sa.String),
        sa.column('publication_year', sa.Integer),
        sa.column('dedup_fingerprint', sa.String),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            editions_t.c.id,
            editions_t.c.title,
            editions_t.c.authors,
            editions_t.c.publication_year,
        )
    )
    for edition_id, title, authors, year in rows:
        bind.execute(
            editions_t.update()
            .where(editions_t.c.id == edition_id)
            .values(dedup_fingerprint=compute_fingerprint(title, authors, year))
        )

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_editions_title_trgm ON editions USING gin (lower(title) gin_trgm_ops)"
    )

    op.add_column(
        'editions',
        sa.Column(
            'search_vector',
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_VECTOR_SQL, persisted=True),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_editions_search_vector', 'editions', ['search_vector'], unique=False, postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_index('ix_editions_search_vector', table_name='editions', postgresql_using='gin')
    op.drop_column('editions', 'search_vector')
    op.execute("DROP INDEX IF EXISTS ix_editions_title_trgm")
    op.drop_index('ix_editions_dedup_fingerprint', table_name='editions')
    op.drop_column('editions', 'dedup_fingerprint')
    # pg_trgm расширение сознательно не удаляется при откате — типовая
    # практика Alembic: расширения не откатывают вместе со схемой.

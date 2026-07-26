from datetime import datetime

from sqlalchemy import Column, Computed, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field, SQLModel

from app.timeutil import utcnow

# Веса: title/authors — A (высший приоритет), subtitle/original_title/series
# — B, publisher — C, description — D. isbn сюда не входит — у него свой
# отдельный точный путь поиска (dedup_fingerprint/isbn), а не полнотекстовый
# (числа/дефисы плохо токенизируются словарём 'russian').
SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(authors, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(subtitle, '')), 'B') || "
    "setweight(to_tsvector('russian', coalesce(original_title, '')), 'B') || "
    "setweight(to_tsvector('russian', coalesce(series, '')), 'B') || "
    "setweight(to_tsvector('russian', coalesce(publisher, '')), 'C') || "
    "setweight(to_tsvector('russian', coalesce(description, '')), 'D')"
)


class Edition(SQLModel, table=True):
    """Библиографическая запись издания."""

    __tablename__ = "editions"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    authors: str | None = Field(default=None, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=300)
    publication_year: int | None = Field(default=None)
    publication_year_text: str | None = Field(default=None, max_length=50)
    isbn: str | None = Field(default=None, max_length=20, index=True)
    language: str | None = Field(default="ru", max_length=10)
    series: str | None = Field(default=None, max_length=300)
    edition_statement: str | None = Field(default=None, max_length=300)
    physical_description: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None)
    # Заполняется явно в роутерах при создании/редактировании (шаг 6, см.
    # app/services/dedup.py) — не через ORM-события, см. ARCHITECTURE.md.
    dedup_fingerprint: str | None = Field(default=None, max_length=1024, index=True)
    # Postgres GENERATED-колонка — заполняется сервером, приложение её
    # никогда не пишет (шаг 6).
    search_vector: str | None = Field(
        default=None, sa_column=Column(TSVECTOR, Computed(SEARCH_VECTOR_SQL, persisted=True))
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (Index("ix_editions_search_vector", "search_vector", postgresql_using="gin"),)

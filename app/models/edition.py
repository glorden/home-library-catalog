from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


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
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

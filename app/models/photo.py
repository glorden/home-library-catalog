from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class PhotoKind(StrEnum):
    COVER = "cover"
    TITLE_PAGE = "title_page"
    TITLE_VERSO = "title_verso"
    SPINE = "spine"
    AUTOGRAPH = "autograph"
    EX_LIBRIS = "ex_libris"
    DAMAGE = "damage"
    OTHER = "other"


class Photo(SQLModel, table=True):
    """Фото экземпляра. Долговременно хранится только kind=cover (шаг 3)."""

    __tablename__ = "photos"

    id: int | None = Field(default=None, primary_key=True)
    copy_id: int = Field(
        sa_column=Column(Integer, ForeignKey("copies.id", ondelete="CASCADE"), nullable=False)
    )
    kind: str = Field(max_length=20)
    file_path: str = Field(max_length=500)
    original_filename: str | None = Field(default=None, max_length=255)
    content_type: str = Field(max_length=50)
    file_size_bytes: int
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class Condition(StrEnum):
    MINT = "mint"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    DAMAGED = "damaged"


class Copy(SQLModel, table=True):
    """Конкретный физический экземпляр издания."""

    __tablename__ = "copies"

    id: int | None = Field(default=None, primary_key=True)
    edition_id: int = Field(
        sa_column=Column(Integer, ForeignKey("editions.id", ondelete="RESTRICT"), nullable=False)
    )
    inventory_code: str | None = Field(default=None, max_length=50, unique=True)
    condition: str | None = Field(default=None, max_length=20)
    acquisition_date: date | None = Field(default=None)
    acquisition_source: str | None = Field(default=None, max_length=300)
    # Приватные поля: не должны попадать ни в один публичный шаблон (шаг 5).
    acquisition_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    storage_location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None)
    public_notes: str | None = Field(default=None)
    has_autograph: bool = Field(default=False)
    has_ex_libris: bool = Field(default=False)
    # opt-out: по умолчанию публичен, владелец явно скрывает то, что не
    # хочет показывать на витрине (шаг 5).
    is_public: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

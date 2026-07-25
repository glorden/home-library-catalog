from datetime import datetime
from enum import StrEnum

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class ProviderName(StrEnum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENAI_COMPATIBLE = "openai_compatible"


class ProviderCredential(SQLModel, table=True):
    """Настройки AI-провайдера для извлечения данных из фото (шаг 4).

    Без user_id: авторизация в проекте — на уровне роутера, не строк, а
    users (шаг 5) всегда будет ровно одной строкой — колонка-владелец
    здесь не добавляла бы никакого поведения."""

    __tablename__ = "provider_credentials"

    id: int | None = Field(default=None, primary_key=True)
    provider: str = Field(max_length=30)
    display_name: str = Field(max_length=100)
    api_key_encrypted: str = Field(max_length=1000)
    base_url: str | None = Field(default=None, max_length=500)
    model_name: str = Field(max_length=100)
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (
        Index(
            "ix_provider_credentials_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class ExtractionCall(SQLModel, table=True):
    """Лог каждой попытки AI-распознавания — закрывает риск №2
    ARCHITECTURE.md (провайдер/токены) и служит основой для дневного
    лимита вызовов (`AI_EXTRACTION_DAILY_LIMIT`). Без `user_id` — по тем
    же причинам, что и у `provider_credentials`: пользователь всегда один,
    колонка-владелец не добавила бы поведения."""

    __tablename__ = "extraction_calls"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    provider: str = Field(max_length=30)
    model_name: str = Field(max_length=100)
    image_count: int
    success: bool
    tokens_input: int | None = Field(default=None)
    tokens_output: int | None = Field(default=None)
    error_message: str | None = Field(default=None)

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.timeutil import utcnow


class User(SQLModel, table=True):
    """Единственный владелец каталога. Ровно одна строка, создаётся CLI
    (`create-admin`), самостоятельной регистрации нет (шаг 5)."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, max_length=255)
    password_hash: str = Field(max_length=255)
    # Инкрементируется в `reset-admin-password` — подписывается в session
    # cookie вместе с user_id, так что сброс пароля инвалидирует уже
    # выданные cookie (нет server-side хранилища сессий для явного отзыва).
    session_version: int = Field(default=1)
    last_login_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

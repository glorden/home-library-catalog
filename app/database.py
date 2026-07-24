from collections.abc import Generator

from sqlmodel import Session, create_engine

from app import models  # noqa: F401  регистрирует таблицы в SQLModel.metadata
from app.config import settings

engine = create_engine(settings.database_url, echo=settings.debug)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

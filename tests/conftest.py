import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.database import get_session
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """Клиент без БД — для маршрутов, не трогающих базу (healthz, hello-world)."""
    return TestClient(app)


@pytest.fixture()
def session():
    """Требует настоящий Postgres по DATABASE_URL (см. docker-compose.yml / CI)."""
    engine = create_engine(settings.database_url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def db_client(session: Session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

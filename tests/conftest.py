import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sa_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.database import get_session
from app.main import app

TEST_DB_NAME = "library_test"


def _test_database_url() -> str:
    url = make_url(settings.database_url).set(database=TEST_DB_NAME)
    return url.render_as_string(hide_password=False)


def _ensure_test_database_exists() -> None:
    """Создаёт library_test при первом запуске, чтобы тесты не сносили дев-БД."""
    admin_url = make_url(settings.database_url).set(database="postgres")
    admin_engine = create_sa_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


@pytest.fixture(autouse=True)
def _isolated_photo_storage(tmp_path, monkeypatch):
    """Фото тестов пишутся во временную папку, а не в реальный data/photos."""
    monkeypatch.setattr(settings, "photo_storage_root", str(tmp_path))


@pytest.fixture(autouse=True)
def _test_settings_extras(monkeypatch):
    """Свежий ключ шифрования на каждый тест + отключаем фоновую очистку
    черновиков (не нужна в тестах и мешала бы TestClient корректно завершаться)."""
    monkeypatch.setattr(settings, "settings_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "enable_draft_cleanup_loop", False)


@pytest.fixture()
def client() -> TestClient:
    """Клиент без БД — для маршрутов, не трогающих базу (healthz, hello-world)."""
    return TestClient(app)


@pytest.fixture()
def session():
    """Требует настоящий Postgres по DATABASE_URL, но работает в отдельной БД
    library_test — не трогает данные, с которыми вы работаете вручную."""
    _ensure_test_database_exists()
    engine = create_engine(_test_database_url())
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

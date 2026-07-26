import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sa_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.database import get_session
from app.dependencies import require_owner
from app.main import app
from app.models import User

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

    # session-фикстура ниже гоняет SQLModel.metadata.create_all(), а не
    # Alembic-миграции — значит расширение pg_trgm (нужно find_candidates
    # для similarity(), шаг 6) само по себе в library_test не появится.
    # IF NOT EXISTS — идемпотентно, безопасно на каждый запуск.
    test_engine = create_sa_engine(_test_database_url(), isolation_level="AUTOCOMMIT")
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    test_engine.dispose()


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
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")


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
def auth_client(session: Session) -> TestClient:
    """Как db_client, но БЕЗ подмены require_owner — для тестов, которые
    сами проверяют реальный auth-флоу (login/logout/редиректы), а не просто
    предполагают авторизованный доступ."""
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def db_client(session: Session) -> TestClient:
    """require_owner подменяется фиктивным (не сохранённым в БД) владельцем —
    все существующие тесты и так предполагают авторизованный доступ; реальный
    login/cookie-флоу отдельно проверяется в test_auth.py через client +
    session напрямую, без этого override."""
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_owner] = lambda: User(
        id=1, email="test@example.com", password_hash="x", session_version=1
    )
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

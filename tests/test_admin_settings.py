from sqlmodel import select

from app.models import ProviderCredential
from app.services import crypto


def _save(
    db_client,
    *,
    provider="claude",
    display_name="Мой Claude",
    api_key="sk-ant-test-secret-value",
    model_name="claude-sonnet-5",
    base_url="",
):
    return db_client.post(
        "/admin/settings",
        data={
            "provider": provider,
            "display_name": display_name,
            "api_key": api_key,
            "model_name": model_name,
            "base_url": base_url,
        },
        follow_redirects=False,
    )


def test_empty_settings_form_renders(db_client):
    response = db_client.get("/admin/settings")
    assert response.status_code == 200
    assert "Настройки сохранены" not in response.text


def test_save_redirects_with_saved_flag_and_shows_confirmation(db_client):
    response = _save(db_client)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/settings?saved=true"

    confirmation_page = db_client.get(response.headers["location"])
    assert "Настройки сохранены" in confirmation_page.text


def test_create_settings_encrypts_key(db_client, session):
    response = _save(db_client, api_key="sk-ant-test-secret-value")
    assert response.status_code == 303

    credentials = session.exec(select(ProviderCredential)).one()
    assert credentials.api_key_encrypted != "sk-ant-test-secret-value"
    assert crypto.decrypt_secret(credentials.api_key_encrypted) == "sk-ant-test-secret-value"
    assert credentials.is_active is True


def test_update_with_blank_api_key_keeps_existing_key(db_client, session):
    _save(db_client, api_key="original-secret")
    credentials = session.exec(select(ProviderCredential)).one()
    original_encrypted = credentials.api_key_encrypted

    _save(db_client, display_name="Мой Claude (переименовано)", api_key="")

    session.refresh(credentials)
    assert credentials.api_key_encrypted == original_encrypted
    assert credentials.display_name == "Мой Claude (переименовано)"


def test_raw_api_key_never_appears_in_settings_page_html(db_client):
    _save(db_client, api_key="sk-ant-should-not-leak")

    response = db_client.get("/admin/settings")
    assert "sk-ant-should-not-leak" not in response.text


def test_create_without_api_key_returns_422(db_client):
    response = _save(db_client, api_key="")
    assert response.status_code == 422


def test_create_unknown_provider_returns_422(db_client):
    response = _save(db_client, provider="not_a_real_provider")
    assert response.status_code == 422


def test_missing_encryption_key_returns_clear_error_not_raw_500(db_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "settings_encryption_key", None)

    response = _save(db_client, api_key="some-key")

    assert response.status_code == 500
    assert "SETTINGS_ENCRYPTION_KEY" in response.text


def test_openai_compatible_requires_base_url(db_client):
    response = _save(
        db_client,
        provider="openai_compatible",
        model_name="qwen/qwen3.6-27b",
        api_key="gsk-test-key",
        base_url="",
    )
    assert response.status_code == 422


def test_openai_compatible_saves_base_url(db_client, session):
    response = _save(
        db_client,
        provider="openai_compatible",
        display_name="Groq (бесплатный)",
        model_name="qwen/qwen3.6-27b",
        api_key="gsk-test-key",
        base_url="https://api.groq.com/openai/v1",
    )
    assert response.status_code == 303

    credentials = session.exec(select(ProviderCredential)).one()
    assert credentials.provider == "openai_compatible"
    assert credentials.base_url == "https://api.groq.com/openai/v1"

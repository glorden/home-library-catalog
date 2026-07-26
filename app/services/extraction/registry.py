import httpx
from sqlmodel import Session, select

from app.config import settings
from app.models.provider_credential import ProviderCredential, ProviderName
from app.schemas.extraction import ExtractionService
from app.services import crypto
from app.services.extraction.base import EXTRACTION_HTTP_TIMEOUT_SECONDS, ExtractionError
from app.services.extraction.claude_provider import ClaudeExtractionService
from app.services.extraction.openai_compatible_provider import OpenAICompatibleExtractionService


def _proxy_http_client() -> httpx.Client | None:
    # Единая точка включения прокси для обоих провайдеров — см. DEPLOY.md,
    # шаг 9 (прод геолоцирован в стране, исключённой из supported-countries
    # у AI-вендоров). Пусто — вызовы идут напрямую, как раньше.
    if not settings.ai_proxy_url:
        return None
    return httpx.Client(proxy=settings.ai_proxy_url, timeout=EXTRACTION_HTTP_TIMEOUT_SECONDS)


def get_extraction_service(credentials: ProviderCredential) -> ExtractionService:
    try:
        api_key = crypto.decrypt_secret(credentials.api_key_encrypted)
    except crypto.EncryptionNotConfiguredError as exc:
        raise ExtractionError(str(exc)) from exc

    http_client = _proxy_http_client()

    if credentials.provider == ProviderName.CLAUDE:
        return ClaudeExtractionService(
            api_key=api_key, model_name=credentials.model_name, http_client=http_client
        )

    if credentials.provider == ProviderName.OPENAI_COMPATIBLE:
        if not credentials.base_url:
            raise ExtractionError("Для OpenAI-совместимого провайдера нужно указать base_url")
        return OpenAICompatibleExtractionService(
            api_key=api_key,
            model_name=credentials.model_name,
            base_url=credentials.base_url,
            http_client=http_client,
        )

    raise ExtractionError(f"Провайдер «{credentials.provider}» пока не поддерживается")


def get_active_extraction_service(session: Session) -> ExtractionService:
    credentials = session.exec(
        select(ProviderCredential).where(ProviderCredential.is_active.is_(True))
    ).first()
    if credentials is None:
        raise ExtractionError("AI-провайдер не настроен — откройте /admin/settings")
    return get_extraction_service(credentials)

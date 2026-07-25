from sqlmodel import Session, select

from app.models.provider_credential import ProviderCredential, ProviderName
from app.schemas.extraction import ExtractionService
from app.services import crypto
from app.services.extraction.base import ExtractionError
from app.services.extraction.claude_provider import ClaudeExtractionService
from app.services.extraction.openai_compatible_provider import OpenAICompatibleExtractionService


def get_extraction_service(credentials: ProviderCredential) -> ExtractionService:
    try:
        api_key = crypto.decrypt_secret(credentials.api_key_encrypted)
    except crypto.EncryptionNotConfiguredError as exc:
        raise ExtractionError(str(exc)) from exc

    if credentials.provider == ProviderName.CLAUDE:
        return ClaudeExtractionService(api_key=api_key, model_name=credentials.model_name)

    if credentials.provider == ProviderName.OPENAI_COMPATIBLE:
        if not credentials.base_url:
            raise ExtractionError("Для OpenAI-совместимого провайдера нужно указать base_url")
        return OpenAICompatibleExtractionService(
            api_key=api_key, model_name=credentials.model_name, base_url=credentials.base_url
        )

    raise ExtractionError(f"Провайдер «{credentials.provider}» пока не поддерживается")


def get_active_extraction_service(session: Session) -> ExtractionService:
    credentials = session.exec(
        select(ProviderCredential).where(ProviderCredential.is_active.is_(True))
    ).first()
    if credentials is None:
        raise ExtractionError("AI-провайдер не настроен — откройте /admin/settings")
    return get_extraction_service(credentials)

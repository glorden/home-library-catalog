from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.dependencies import SessionDep, require_owner
from app.models.provider_credential import ProviderCredential, ProviderName
from app.services import crypto
from app.timeutil import utcnow

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(
    prefix="/admin/settings", tags=["settings"], dependencies=[Depends(require_owner)]
)

SUPPORTED_PROVIDERS = {ProviderName.CLAUDE.value, ProviderName.OPENAI_COMPATIBLE.value}


@dataclass
class ProviderSettingsFormData:
    provider: str
    display_name: str
    api_key: str
    model_name: str
    base_url: str | None


def provider_settings_form(
    provider: str = Form(ProviderName.CLAUDE.value),
    display_name: str = Form(...),
    api_key: str = Form(""),
    model_name: str = Form(...),
    base_url: str = Form(""),
) -> ProviderSettingsFormData:
    return ProviderSettingsFormData(
        provider=provider,
        display_name=display_name,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url.strip() or None,
    )


ProviderSettingsFormDep = Annotated[ProviderSettingsFormData, Depends(provider_settings_form)]


def _get_credentials(session: Session) -> ProviderCredential | None:
    return session.exec(select(ProviderCredential)).first()


def _encrypt_or_422(api_key: str) -> str:
    try:
        return crypto.encrypt_secret(api_key)
    except crypto.EncryptionNotConfiguredError as exc:
        raise HTTPException(
            status_code=500,
            detail="Сервер не настроен: переменная окружения SETTINGS_ENCRYPTION_KEY не задана",
        ) from exc


@router.get("")
def settings_form(request: Request, session: SessionDep):
    credentials = _get_credentials(session)
    return templates.TemplateResponse(
        request, "admin/settings_form.html", {"credentials": credentials}
    )


@router.post("")
def save_settings(data: ProviderSettingsFormDep, session: SessionDep):
    if data.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422, detail=f"Провайдер «{data.provider}» пока не поддерживается"
        )
    if data.provider == ProviderName.OPENAI_COMPATIBLE.value and not data.base_url:
        raise HTTPException(
            status_code=422, detail="Для OpenAI-совместимого провайдера нужно указать base_url"
        )

    credentials = _get_credentials(session)
    if credentials is None:
        if not data.api_key.strip():
            raise HTTPException(status_code=422, detail="Укажите API-ключ")
        credentials = ProviderCredential(
            provider=data.provider,
            display_name=data.display_name,
            api_key_encrypted=_encrypt_or_422(data.api_key),
            model_name=data.model_name,
            base_url=data.base_url,
            is_active=True,
        )
        session.add(credentials)
    else:
        credentials.provider = data.provider
        credentials.display_name = data.display_name
        credentials.model_name = data.model_name
        credentials.base_url = data.base_url
        credentials.is_active = True
        if data.api_key.strip():
            credentials.api_key_encrypted = _encrypt_or_422(data.api_key)
        credentials.updated_at = utcnow()
        session.add(credentials)

    session.commit()
    return RedirectResponse("/admin/settings", status_code=303)

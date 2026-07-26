import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.config import settings
from app.dependencies import SessionDep, require_owner
from app.models import Copy, Edition
from app.routers.admin_copies import attach_cover_photo
from app.routers.admin_editions import EditionFormDep
from app.schemas.extraction import ExtractionImage, ExtractionService
from app.services import extraction_log, photo_storage
from app.services.extraction import registry
from app.services.extraction.base import ExtractionError

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(
    prefix="/admin/extract", tags=["extraction"], dependencies=[Depends(require_owner)]
)


def _extraction_service_dep(session: SessionDep) -> ExtractionService:
    try:
        return registry.get_active_extraction_service(session)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


ExtractionServiceDep = Annotated[ExtractionService, Depends(_extraction_service_dep)]


@router.get("/new")
def new_extraction_form(request: Request):
    return templates.TemplateResponse(request, "admin/extract_upload.html", {})


@router.post("/recognize")
def recognize(
    request: Request,
    session: SessionDep,
    service: ExtractionServiceDep,
    cover: Annotated[UploadFile, File()],
    title_page: Annotated[UploadFile, File()],
    title_verso: Annotated[UploadFile, File()],
):
    if extraction_log.count_calls_today(session) >= settings.ai_extraction_daily_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Дневной лимит AI-вызовов исчерпан "
                f"({settings.ai_extraction_daily_limit}/день). Попробуйте завтра."
            ),
        )

    draft_id = secrets.token_hex(16)
    uploads = dict(zip(photo_storage.DRAFT_KINDS, (cover, title_page, title_verso), strict=True))

    try:
        for kind, upload in uploads.items():
            photo_storage.save_draft_image(draft_id, kind, upload)
    except photo_storage.InvalidImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    images = [
        ExtractionImage(kind=kind, content=photo_storage.read_draft_image(draft_id, kind))
        for kind in uploads
    ]
    try:
        result = service.extract(images, language_hint="ru")
    except ExtractionError as exc:
        # Каждая попытка, дошедшая до провайдера, считается в дневной лимит
        # независимо от исхода — иначе баг/цикл продолжит жечь ключ, просто
        # не переставая логироваться.
        extraction_log.log_call(
            session,
            provider=service.provider_name,
            model_name=service.model_name,
            image_count=len(images),
            success=False,
            error_message=str(exc),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    extraction_log.log_call(
        session,
        provider=result.provider_name,
        model_name=result.model_name,
        image_count=len(images),
        success=True,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
    )

    return templates.TemplateResponse(
        request, "admin/extraction_confirm.html", {"result": result, "draft_id": draft_id}
    )


def _attach_draft_cover(session: Session, copy_id: int, draft_id: str) -> None:
    cover_path = photo_storage.resolve_draft_path(draft_id, "cover")
    with open(cover_path, "rb") as fh:
        attach_cover_photo(session, copy_id, UploadFile(file=fh, filename="cover.jpg"))


@router.post("/{draft_id}/confirm")
def confirm_extraction(draft_id: str, data: EditionFormDep, session: SessionDep):
    try:
        cover_path = photo_storage.resolve_draft_path(draft_id, "cover")
    except photo_storage.InvalidDraftIdError:
        raise HTTPException(status_code=404) from None
    if not cover_path.exists():
        raise HTTPException(
            status_code=404, detail="Черновик не найден или устарел, начните заново"
        )

    edition = Edition(**asdict(data))
    session.add(edition)
    session.commit()
    session.refresh(edition)

    copy = Copy(edition_id=edition.id)
    session.add(copy)
    session.commit()
    session.refresh(copy)

    _attach_draft_cover(session, copy.id, draft_id)
    photo_storage.delete_draft(draft_id)

    return RedirectResponse(f"/admin/editions/{edition.id}", status_code=303)

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.dependencies import SessionDep
from app.models import Copy, Edition, Photo
from app.services import photo_storage
from app.timeutil import utcnow

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(tags=["copies"])


@dataclass
class CopyFormData:
    inventory_code: str | None
    condition: str | None
    acquisition_date: date | None
    acquisition_source: str | None
    acquisition_price: Decimal | None
    storage_location: str | None
    notes: str | None
    public_notes: str | None
    has_autograph: bool
    has_ex_libris: bool


def copy_form(
    inventory_code: str = Form(""),
    condition: str = Form(""),
    acquisition_date: str = Form(""),
    acquisition_source: str = Form(""),
    acquisition_price: str = Form(""),
    storage_location: str = Form(""),
    notes: str = Form(""),
    public_notes: str = Form(""),
    has_autograph: bool = Form(False),
    has_ex_libris: bool = Form(False),
) -> CopyFormData:
    price = None
    if acquisition_price.strip():
        try:
            price = Decimal(acquisition_price)
        except InvalidOperation:
            raise HTTPException(status_code=422, detail="Некорректная цена") from None
    return CopyFormData(
        inventory_code=inventory_code or None,
        condition=condition or None,
        acquisition_date=date.fromisoformat(acquisition_date) if acquisition_date.strip() else None,
        acquisition_source=acquisition_source or None,
        acquisition_price=price,
        storage_location=storage_location or None,
        notes=notes or None,
        public_notes=public_notes or None,
        has_autograph=has_autograph,
        has_ex_libris=has_ex_libris,
    )


CopyFormDep = Annotated[CopyFormData, Depends(copy_form)]


def _get_cover_photo(session: Session, copy_id: int) -> Photo | None:
    return session.exec(
        select(Photo).where(Photo.copy_id == copy_id, Photo.kind == "cover")
    ).first()


def attach_cover_photo(session: Session, copy_id: int, upload: UploadFile) -> None:
    try:
        meta = photo_storage.save_cover_photo(copy_id, upload)
    except photo_storage.InvalidImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    photo = Photo(
        copy_id=copy_id,
        kind="cover",
        file_path=meta.file_path,
        original_filename=upload.filename,
        content_type=meta.content_type,
        file_size_bytes=meta.file_size_bytes,
        width=meta.width,
        height=meta.height,
    )
    session.add(photo)
    session.commit()


def _delete_copy_photos(session: Session, copy_id: int) -> None:
    photos = session.exec(select(Photo).where(Photo.copy_id == copy_id)).all()
    for photo in photos:
        photo_storage.delete_photo_file(photo.file_path)


@router.get("/admin/editions/{edition_id}/copies/new")
def new_copy_form(edition_id: int, request: Request, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/copy_form.html", {"edition": edition, "copy": None, "cover_photo": None}
    )


@router.post("/admin/editions/{edition_id}/copies")
def create_copy(
    edition_id: int,
    data: CopyFormDep,
    session: SessionDep,
    cover_photo: Annotated[UploadFile | None, File()] = None,
):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    copy = Copy(edition_id=edition_id, **asdict(data))
    session.add(copy)
    session.commit()
    session.refresh(copy)

    if cover_photo is not None and cover_photo.filename:
        attach_cover_photo(session, copy.id, cover_photo)

    return RedirectResponse(f"/admin/editions/{edition_id}", status_code=303)


@router.get("/admin/copies/{copy_id}/edit")
def edit_copy_form(copy_id: int, request: Request, session: SessionDep):
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404)
    edition = session.get(Edition, copy.edition_id)
    cover_photo = _get_cover_photo(session, copy_id)
    return templates.TemplateResponse(
        request,
        "admin/copy_form.html",
        {"edition": edition, "copy": copy, "cover_photo": cover_photo},
    )


@router.post("/admin/copies/{copy_id}")
def update_copy(
    copy_id: int,
    data: CopyFormDep,
    session: SessionDep,
    cover_photo: Annotated[UploadFile | None, File()] = None,
):
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404)
    for field, value in asdict(data).items():
        setattr(copy, field, value)
    copy.updated_at = utcnow()
    session.add(copy)
    session.commit()

    if cover_photo is not None and cover_photo.filename:
        existing = _get_cover_photo(session, copy_id)
        if existing is not None:
            photo_storage.delete_photo_file(existing.file_path)
            session.delete(existing)
            session.commit()
        attach_cover_photo(session, copy_id, cover_photo)

    return RedirectResponse(f"/admin/editions/{copy.edition_id}", status_code=303)


@router.delete("/admin/copies/{copy_id}")
def delete_copy(copy_id: int, session: SessionDep):
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404)
    _delete_copy_photos(session, copy_id)
    session.delete(copy)
    session.commit()
    return ""

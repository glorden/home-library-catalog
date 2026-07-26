from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.dependencies import SessionDep, require_owner
from app.models import Copy, Edition, Photo
from app.services import dedup, search
from app.timeutil import utcnow

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(
    prefix="/admin/editions", tags=["editions"], dependencies=[Depends(require_owner)]
)


@dataclass
class EditionFormData:
    title: str
    subtitle: str | None
    original_title: str | None
    authors: str | None
    publisher: str | None
    publication_year: int | None
    publication_year_text: str | None
    isbn: str | None
    language: str | None
    series: str | None
    edition_statement: str | None
    physical_description: str | None
    description: str | None


def edition_form(
    title: str = Form(...),
    subtitle: str = Form(""),
    original_title: str = Form(""),
    authors: str = Form(""),
    publisher: str = Form(""),
    publication_year: str = Form(""),
    publication_year_text: str = Form(""),
    isbn: str = Form(""),
    language: str = Form("ru"),
    series: str = Form(""),
    edition_statement: str = Form(""),
    physical_description: str = Form(""),
    description: str = Form(""),
) -> EditionFormData:
    return EditionFormData(
        title=title,
        subtitle=subtitle or None,
        original_title=original_title or None,
        authors=authors or None,
        publisher=publisher or None,
        publication_year=int(publication_year) if publication_year.strip() else None,
        publication_year_text=publication_year_text or None,
        isbn=isbn or None,
        language=language or None,
        series=series or None,
        edition_statement=edition_statement or None,
        physical_description=physical_description or None,
        description=description or None,
    )


EditionFormDep = Annotated[EditionFormData, Depends(edition_form)]


def create_edition_from_form(session: Session, data: EditionFormData) -> Edition:
    """Общий путь создания Edition из формы — используется и ручным
    добавлением (create_edition), и AI-подтверждением
    (extraction.py::confirm_extraction), чтобы dedup_fingerprint
    проставлялся ровно в одном месте, а не дублировался по обеим веткам."""
    edition = Edition(**asdict(data))
    dedup.apply_fingerprint(edition)
    session.add(edition)
    session.commit()
    session.refresh(edition)
    return edition


@router.get("")
def list_editions(request: Request, session: SessionDep, q: str = ""):
    editions = search.search_editions(session, q, public_only=False)
    return templates.TemplateResponse(
        request, "admin/editions_list.html", {"editions": editions, "q": q}
    )


@router.get("/new")
def new_edition_form(request: Request):
    return templates.TemplateResponse(request, "admin/edition_form.html", {"edition": None})


@router.get("/dedup-candidates")
def dedup_candidates_fragment(
    request: Request,
    session: SessionDep,
    title: str = "",
    authors: str = "",
    publication_year: str = "",
    isbn: str = "",
    exclude_edition_id: str = "",
):
    # Дёргается на каждое нажатие клавиши (htmx), в т.ч. с "недопечатанным"
    # вводом — разбор года/id должен быть терпимым, никогда не 422-ить,
    # в отличие от боевой формы сохранения (edition_form ниже).
    candidates = dedup.find_candidates(
        session,
        title=title,
        authors=authors or None,
        year=int(publication_year) if publication_year.strip().isdigit() else None,
        isbn=isbn or None,
        exclude_edition_id=(
            int(exclude_edition_id) if exclude_edition_id.strip().isdigit() else None
        ),
    )
    return templates.TemplateResponse(
        request, "admin/partials/dedup_candidates.html", {"candidates": candidates}
    )


@router.post("")
def create_edition(data: EditionFormDep, session: SessionDep):
    edition = create_edition_from_form(session, data)
    return RedirectResponse(f"/admin/editions/{edition.id}", status_code=303)


@router.get("/{edition_id}")
def edition_detail(edition_id: int, request: Request, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    copies = session.exec(select(Copy).where(Copy.edition_id == edition_id)).all()
    cover_photos = {}
    if copies:
        copy_ids = [copy.id for copy in copies]
        photos = session.exec(
            select(Photo).where(Photo.copy_id.in_(copy_ids), Photo.kind == "cover")
        ).all()
        cover_photos = {photo.copy_id: photo for photo in photos}
    return templates.TemplateResponse(
        request,
        "admin/edition_detail.html",
        {"edition": edition, "copies": copies, "cover_photos": cover_photos},
    )


@router.get("/{edition_id}/edit")
def edit_edition_form(edition_id: int, request: Request, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "admin/edition_form.html", {"edition": edition})


@router.post("/{edition_id}")
def update_edition(edition_id: int, data: EditionFormDep, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    for field, value in asdict(data).items():
        setattr(edition, field, value)
    edition.updated_at = utcnow()
    dedup.apply_fingerprint(edition)
    session.add(edition)
    session.commit()
    return RedirectResponse(f"/admin/editions/{edition.id}", status_code=303)


@router.delete("/{edition_id}")
def delete_edition(edition_id: int, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    try:
        session.delete(edition)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить издание, пока у него есть экземпляры",
        ) from None
    return ""

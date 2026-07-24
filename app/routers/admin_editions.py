from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.dependencies import SessionDep
from app.models import Copy, Edition
from app.timeutil import utcnow

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(prefix="/admin/editions", tags=["editions"])


@dataclass
class EditionFormData:
    title: str
    subtitle: str | None
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


@router.get("")
def list_editions(request: Request, session: SessionDep):
    editions = session.exec(select(Edition).order_by(Edition.title)).all()
    return templates.TemplateResponse(request, "admin/editions_list.html", {"editions": editions})


@router.get("/new")
def new_edition_form(request: Request):
    return templates.TemplateResponse(request, "admin/edition_form.html", {"edition": None})


@router.post("")
def create_edition(data: EditionFormDep, session: SessionDep):
    edition = Edition(**asdict(data))
    session.add(edition)
    session.commit()
    session.refresh(edition)
    return RedirectResponse(f"/admin/editions/{edition.id}", status_code=303)


@router.get("/{edition_id}")
def edition_detail(edition_id: int, request: Request, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    copies = session.exec(select(Copy).where(Copy.edition_id == edition_id)).all()
    return templates.TemplateResponse(
        request, "admin/edition_detail.html", {"edition": edition, "copies": copies}
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

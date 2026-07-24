from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import SessionDep
from app.models import Copy, Edition

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


@router.get("/admin/editions/{edition_id}/copies/new")
def new_copy_form(edition_id: int, request: Request, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/copy_form.html", {"edition": edition, "copy": None}
    )


@router.post("/admin/editions/{edition_id}/copies")
def create_copy(edition_id: int, data: CopyFormDep, session: SessionDep):
    edition = session.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404)
    copy = Copy(edition_id=edition_id, **asdict(data))
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return RedirectResponse(f"/admin/editions/{edition_id}", status_code=303)


@router.get("/admin/copies/{copy_id}/edit")
def edit_copy_form(copy_id: int, request: Request, session: SessionDep):
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404)
    edition = session.get(Edition, copy.edition_id)
    return templates.TemplateResponse(
        request, "admin/copy_form.html", {"edition": edition, "copy": copy}
    )


@router.post("/admin/copies/{copy_id}")
def update_copy(copy_id: int, data: CopyFormDep, session: SessionDep):
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404)
    for field, value in asdict(data).items():
        setattr(copy, field, value)
    copy.updated_at = datetime.utcnow()
    session.add(copy)
    session.commit()
    return RedirectResponse(f"/admin/editions/{copy.edition_id}", status_code=303)


@router.delete("/admin/copies/{copy_id}")
def delete_copy(copy_id: int, session: SessionDep):
    copy = session.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=404)
    session.delete(copy)
    session.commit()
    return ""

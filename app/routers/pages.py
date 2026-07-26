from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from app.config import settings
from app.dependencies import SessionDep
from app.models import Copy, Edition, Photo
from app.services import search

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
SERVICE_WORKER_PATH = BASE_DIR / "static" / "js" / "sw.js"

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def home(request: Request, session: SessionDep, q: str = ""):
    if not settings.showcase_public:
        return templates.TemplateResponse(request, "pages/home.html", {"closed": True})
    editions = search.search_editions(session, q, public_only=True)
    covers = search.covers_for_editions(session, editions)
    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {
            "closed": False,
            "editions_with_covers": [(edition, covers.get(edition.id)) for edition in editions],
            "q": q,
        },
    )


@router.get("/catalog/{edition_id}")
def catalog_detail(edition_id: int, request: Request, session: SessionDep):
    if not settings.showcase_public:
        raise HTTPException(status_code=404)
    edition = session.get(Edition, edition_id)
    public_copies = (
        session.exec(
            select(Copy).where(Copy.edition_id == edition_id, Copy.is_public.is_(True))
        ).all()
        if edition is not None
        else []
    )
    # Нет издания или нет ни одного публичного экземпляра — 404 без
    # разницы между случаями: приватные вещи не должны палить сам факт
    # своего существования (риск №6 ARCHITECTURE.md).
    if edition is None or not public_copies:
        raise HTTPException(status_code=404)
    copy_ids = [copy.id for copy in public_copies]
    cover = session.exec(
        select(Photo).where(Photo.copy_id.in_(copy_ids), Photo.kind == "cover")
    ).first()
    return templates.TemplateResponse(
        request,
        "pages/catalog_detail.html",
        {"edition": edition, "copies": public_copies, "cover": cover},
    )


@router.get("/offline.html")
def offline(request: Request):
    # Обычный роут, не только SW-заглушка: sw.js кладёт этот же URL в кэш
    # при install (см. app/static/js/sw.js), но страница должна отдаваться
    # и по прямому заходу, пока сеть есть.
    return templates.TemplateResponse(request, "pages/offline.html", {})


@router.get("/sw.js")
def service_worker() -> Response:
    # Обязательно с корневого пути, а не /static/sw.js — scope service
    # worker'а по умолчанию равен директории, откуда он отдан; под /static/
    # он не смог бы перехватывать навигации на "/", "/catalog/*" и т.д.
    return Response(
        content=SERVICE_WORKER_PATH.read_text(encoding="utf-8"),
        media_type="text/javascript",
        headers={"Cache-Control": "no-cache"},
    )

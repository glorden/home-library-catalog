from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.config import settings
from app.dependencies import SessionDep
from app.models import Copy, Edition, Photo

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _public_editions_with_covers(session: Session) -> list[tuple[Edition, Photo | None]]:
    """Издания с хотя бы одним публичным экземпляром + обложка одного из
    них, одним батч-запросом (не N+1) — зеркалит паттерн из
    admin_editions.py::edition_detail."""
    editions = session.exec(
        select(Edition)
        .join(Copy)
        .where(Copy.is_public.is_(True))
        .distinct()
        .order_by(Edition.title)
    ).all()
    covers: dict[int, Photo] = {}
    if editions:
        edition_ids = [edition.id for edition in editions]
        public_copies = session.exec(
            select(Copy).where(Copy.edition_id.in_(edition_ids), Copy.is_public.is_(True))
        ).all()
        copy_to_edition = {copy.id: copy.edition_id for copy in public_copies}
        copy_ids = list(copy_to_edition)
        if copy_ids:
            photos = session.exec(
                select(Photo).where(Photo.copy_id.in_(copy_ids), Photo.kind == "cover")
            ).all()
            for photo in photos:
                covers.setdefault(copy_to_edition[photo.copy_id], photo)
    return [(edition, covers.get(edition.id)) for edition in editions]


@router.get("/")
def home(request: Request, session: SessionDep):
    if not settings.showcase_public:
        return templates.TemplateResponse(request, "pages/home.html", {"closed": True})
    editions_with_covers = _public_editions_with_covers(session)
    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {"closed": False, "editions_with_covers": editions_with_covers},
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

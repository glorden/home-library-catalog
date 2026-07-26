from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from app.dependencies import CurrentUserDep, SessionDep, require_owner
from app.models import Copy, Photo
from app.services import photo_storage

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/photos/{photo_id}")
def serve_photo(photo_id: int, session: SessionDep, current_user: CurrentUserDep):
    photo = session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404)
    if current_user is None:
        # Не владелец: доступна только обложка публичного экземпляра — без
        # намёка на существование приватных вещей (404, не 403).
        copy = session.get(Copy, photo.copy_id)
        if photo.kind != "cover" or copy is None or not copy.is_public:
            raise HTTPException(status_code=404)
    path = photo_storage.resolve_path(photo.file_path)
    if not path.exists():
        raise HTTPException(status_code=404)
    # За Caddy (шаг 8) — не отдаём байты сами, а просим прокси отдать файл.
    # Без этого is_public ничего не значит: любую обложку можно было бы
    # скачать напрямую мимо проверки прав выше. В Caddyfile это не
    # отдельный внешний роут (в отличие от nginx internal;) — реагирует
    # на заголовок только вложенный handle_response того же запроса,
    # поэтому префикс не нужен: значение должно быть путём относительно
    # смонтированного в Caddy /data/photos, как и есть в file_path.
    return Response(
        media_type=photo.content_type,
        headers={"X-Accel-Redirect": f"/{photo.file_path}"},
    )


@router.get("/drafts/{draft_id}/{kind}", dependencies=[Depends(require_owner)])
def serve_draft_photo(draft_id: str, kind: str):
    try:
        path = photo_storage.resolve_draft_path(draft_id, kind)
    except photo_storage.InvalidDraftIdError:
        raise HTTPException(status_code=404) from None
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")

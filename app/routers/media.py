from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

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
    return FileResponse(path, media_type=photo.content_type)


@router.get("/drafts/{draft_id}/{kind}", dependencies=[Depends(require_owner)])
def serve_draft_photo(draft_id: str, kind: str):
    try:
        path = photo_storage.resolve_draft_path(draft_id, kind)
    except photo_storage.InvalidDraftIdError:
        raise HTTPException(status_code=404) from None
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")

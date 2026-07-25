from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.dependencies import SessionDep
from app.models import Photo
from app.services import photo_storage

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/photos/{photo_id}")
def serve_photo(photo_id: int, session: SessionDep):
    photo = session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404)
    path = photo_storage.resolve_path(photo.file_path)
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type=photo.content_type)


@router.get("/drafts/{draft_id}/{kind}")
def serve_draft_photo(draft_id: str, kind: str):
    try:
        path = photo_storage.resolve_draft_path(draft_id, kind)
    except photo_storage.InvalidDraftIdError:
        raise HTTPException(status_code=404) from None
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")

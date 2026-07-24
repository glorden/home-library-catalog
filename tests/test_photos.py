import io

from PIL import Image
from sqlmodel import select

from app.models import Copy, Photo
from app.services import photo_storage


def _create_edition(db_client) -> int:
    response = db_client.post(
        "/admin/editions", data={"title": "Издание с фото"}, follow_redirects=False
    )
    return int(response.headers["location"].rsplit("/", 1)[-1])


def _fake_jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), color="red").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_upload_cover_photo_is_served(db_client, session):
    edition_id = _create_edition(db_client)

    response = db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "PHOTO-001"},
        files={"cover_photo": ("cover.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    photo = session.exec(select(Photo).where(Photo.copy_id == copy.id)).one()
    assert photo.kind == "cover"
    assert photo.content_type == "image/jpeg"

    photo_response = db_client.get(f"/media/photos/{photo.id}")
    assert photo_response.status_code == 200
    assert photo_response.headers["content-type"] == "image/jpeg"


def test_replacing_cover_photo_deletes_old_file(db_client, session):
    edition_id = _create_edition(db_client)
    db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "PHOTO-002"},
        files={"cover_photo": ("cover.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    old_photo = session.exec(select(Photo).where(Photo.copy_id == copy.id)).one()
    old_path = photo_storage.resolve_path(old_photo.file_path)
    assert old_path.exists()

    db_client.post(
        f"/admin/copies/{copy.id}",
        data={"inventory_code": "PHOTO-002"},
        files={"cover_photo": ("new_cover.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )

    assert not old_path.exists()
    photos = session.exec(select(Photo).where(Photo.copy_id == copy.id)).all()
    assert len(photos) == 1


def test_deleting_copy_removes_photo_file(db_client, session):
    edition_id = _create_edition(db_client)
    db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "PHOTO-003"},
        files={"cover_photo": ("cover.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    photo = session.exec(select(Photo).where(Photo.copy_id == copy.id)).one()
    path = photo_storage.resolve_path(photo.file_path)
    assert path.exists()

    delete_response = db_client.delete(f"/admin/copies/{copy.id}")
    assert delete_response.status_code == 200
    assert not path.exists()


def test_invalid_image_upload_returns_422(db_client):
    edition_id = _create_edition(db_client)

    response = db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "PHOTO-004"},
        files={"cover_photo": ("not_an_image.jpg", b"this is not a jpeg", "image/jpeg")},
        follow_redirects=False,
    )
    assert response.status_code == 422

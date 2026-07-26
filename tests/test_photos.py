import io

from PIL import Image
from sqlmodel import select

from app.dependencies import get_current_user
from app.main import app
from app.models import Copy, Photo, User
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
        # Как настоящий чекбокс в браузере: не отправлен — не публичен.
        # Тестовый POST не рендерит форму, поэтому is_public нужно указать явно.
        data={"inventory_code": "PHOTO-001", "is_public": "true"},
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
    # Caddy (шаг 8) отдаёт сам файл по этому заголовку — TestClient его не
    # интерпретирует, поэтому здесь проверяем именно заголовок, а не байты.
    assert photo_response.headers["x-accel-redirect"] == f"/{photo.file_path}"


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


def test_private_copy_cover_hidden_from_anonymous_visitor(db_client, session):
    edition_id = _create_edition(db_client)
    db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "PHOTO-005"},
        files={"cover_photo": ("cover.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    copy.is_public = False
    session.add(copy)
    session.commit()
    photo = session.exec(select(Photo).where(Photo.copy_id == copy.id)).one()

    # db_client подменяет require_owner, но не get_current_user — serve_photo
    # видит анонимного посетителя (request.state.user is None), как и в проде.
    response = db_client.get(f"/media/photos/{photo.id}")
    assert response.status_code == 404


def test_private_copy_cover_visible_to_owner(db_client, session):
    edition_id = _create_edition(db_client)
    db_client.post(
        f"/admin/editions/{edition_id}/copies",
        data={"inventory_code": "PHOTO-006"},
        files={"cover_photo": ("cover.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    copy = session.exec(select(Copy).where(Copy.edition_id == edition_id)).one()
    copy.is_public = False
    session.add(copy)
    session.commit()
    photo = session.exec(select(Photo).where(Photo.copy_id == copy.id)).one()

    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, email="owner@example.com", password_hash="x", session_version=1
    )
    response = db_client.get(f"/media/photos/{photo.id}")
    assert response.status_code == 200


def test_draft_photo_requires_owner(client):
    response = client.get(f"/media/drafts/{'a' * 32}/cover", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

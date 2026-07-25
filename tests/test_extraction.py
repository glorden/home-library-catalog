import io
import re

from PIL import Image
from sqlmodel import select

from app.main import app
from app.models import Copy, Edition, Photo
from app.routers.extraction import _extraction_service_dep
from app.schemas.extraction import ExtractedField, ExtractionResult
from app.services import photo_storage
from app.services.extraction.base import ExtractionError
from tests.fakes import FakeExtractionService

DRAFT_ID_PATTERN = re.compile(r"/admin/extract/([0-9a-f]{32})/confirm")


def _fake_jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), color="blue").save(buffer, format="JPEG")
    return buffer.getvalue()


def _photo_files() -> dict:
    jpeg = _fake_jpeg_bytes()
    return {
        "cover": ("cover.jpg", jpeg, "image/jpeg"),
        "title_page": ("title_page.jpg", jpeg, "image/jpeg"),
        "title_verso": ("title_verso.jpg", jpeg, "image/jpeg"),
    }


def _use_fake_service(fake: FakeExtractionService) -> None:
    app.dependency_overrides[_extraction_service_dep] = lambda: fake


def _extract_draft_id(html: str) -> str:
    match = DRAFT_ID_PATTERN.search(html)
    assert match, "draft_id не найден в HTML формы подтверждения"
    return match.group(1)


def test_recognize_prefills_confirmation_form_and_handles_null_value(db_client):
    fake = FakeExtractionService(
        result=ExtractionResult(
            title=ExtractedField(value="Война и мир", confidence=0.95),
            isbn=ExtractedField(value=None, confidence=None),
            provider_name="fake",
            model_name="fake-model",
        )
    )
    _use_fake_service(fake)

    response = db_client.post("/admin/extract/recognize", files=_photo_files())

    assert response.status_code == 200
    assert "Война и мир" in response.text
    assert "None" not in response.text
    assert len(fake.calls) == 1
    assert len(fake.calls[0]) == 3


def test_confirm_saves_user_edits_and_keeps_only_cover_photo(db_client, session):
    fake = FakeExtractionService(
        result=ExtractionResult(
            title=ExtractedField(value="AI-название", confidence=0.9),
            provider_name="fake",
            model_name="fake-model",
        )
    )
    _use_fake_service(fake)

    recognize_response = db_client.post("/admin/extract/recognize", files=_photo_files())
    draft_id = _extract_draft_id(recognize_response.text)
    assert photo_storage.draft_dir(draft_id).exists()

    confirm_response = db_client.post(
        f"/admin/extract/{draft_id}/confirm",
        data={"title": "Исправленное пользователем название"},
        follow_redirects=False,
    )
    assert confirm_response.status_code == 303

    edition = session.exec(select(Edition)).one()
    # Подтверждаем принцип «AI не пишет в базу без подтверждения»: в базе — правка
    # пользователя, а не сырой ответ AI.
    assert edition.title == "Исправленное пользователем название"

    copy = session.exec(select(Copy).where(Copy.edition_id == edition.id)).one()
    photos = session.exec(select(Photo).where(Photo.copy_id == copy.id)).all()
    assert len(photos) == 1
    assert photos[0].kind == "cover"

    assert not photo_storage.draft_dir(draft_id).exists()


def test_extraction_error_returns_422_and_keeps_draft_files(db_client, tmp_path):
    fake = FakeExtractionService(raise_error=ExtractionError("сервис недоступен"))
    _use_fake_service(fake)

    response = db_client.post("/admin/extract/recognize", files=_photo_files())

    assert response.status_code == 422
    draft_dirs = list((tmp_path / "_drafts").iterdir())
    assert len(draft_dirs) == 1
    assert (draft_dirs[0] / "cover.jpg").exists()
    assert (draft_dirs[0] / "title_page.jpg").exists()
    assert (draft_dirs[0] / "title_verso.jpg").exists()


def test_confirm_with_nonexistent_draft_returns_404(db_client):
    response = db_client.post(
        f"/admin/extract/{'a' * 32}/confirm",
        data={"title": "Не должно сохраниться"},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_confirm_with_malformed_draft_id_returns_404(db_client):
    response = db_client.post(
        "/admin/extract/not-a-valid-draft-id/confirm",
        data={"title": "Не должно сохраниться"},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_recognize_without_configured_provider_returns_422(db_client):
    response = db_client.post("/admin/extract/recognize", files=_photo_files())
    assert response.status_code == 422

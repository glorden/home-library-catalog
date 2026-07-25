import re
import secrets
import shutil
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from app.config import settings
from app.timeutil import utcnow

register_heif_opener()

MAX_DIMENSION = 1600
# Выше, чем у обложки, — старым титульным листам нужно больше разрешения для AI-распознавания.
DRAFT_MAX_DIMENSION = 2400
JPEG_QUALITY = 85
DRAFT_DIR_NAME = "_drafts"
DRAFT_KINDS = ("cover", "title_page", "title_verso")

# draft_id всегда generated сервером через secrets.token_hex(16), но приходит
# обратно от клиента (URL пути /admin/extract/{draft_id}/confirm,
# /media/drafts/{draft_id}/{kind}) — проверка формата закрывает path traversal
# (".." и т.п.) до того, как значение попадёт в путь на диске.
_DRAFT_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class InvalidImageError(Exception):
    pass


class InvalidDraftIdError(Exception):
    pass


@dataclass
class PhotoMeta:
    file_path: str
    content_type: str
    file_size_bytes: int
    width: int
    height: int


def _storage_root() -> Path:
    return Path(settings.photo_storage_root)


def resolve_path(relative_path: str) -> Path:
    return _storage_root() / relative_path


def _process_image(upload: UploadFile, max_dimension: int) -> Image.Image:
    """Применяет EXIF-ориентацию, затем полностью отбрасывает EXIF (в т.ч. GPS) и ресайзит."""
    try:
        image = Image.open(upload.file)
        image.load()
    except UnidentifiedImageError as exc:
        raise InvalidImageError("Не удалось распознать изображение") from exc

    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image.thumbnail((max_dimension, max_dimension))
    return image


def save_cover_photo(copy_id: int, upload: UploadFile) -> PhotoMeta:
    """Обрабатывает и сохраняет фото обложки как JPEG в постоянное хранилище."""
    image = _process_image(upload, MAX_DIMENSION)

    now = utcnow()
    relative_dir = Path(f"{now:%Y}/{now:%m}/copy_{copy_id}")
    (_storage_root() / relative_dir).mkdir(parents=True, exist_ok=True)
    relative_path = relative_dir / f"cover_{secrets.token_hex(8)}.jpg"

    full_path = _storage_root() / relative_path
    image.save(full_path, format="JPEG", quality=JPEG_QUALITY)

    return PhotoMeta(
        file_path=str(relative_path).replace("\\", "/"),
        content_type="image/jpeg",
        file_size_bytes=full_path.stat().st_size,
        width=image.width,
        height=image.height,
    )


def delete_photo_file(file_path: str) -> None:
    resolve_path(file_path).unlink(missing_ok=True)


def draft_dir(draft_id: str) -> Path:
    if not _DRAFT_ID_RE.fullmatch(draft_id):
        raise InvalidDraftIdError("Некорректный draft_id")
    return _storage_root() / DRAFT_DIR_NAME / draft_id


def resolve_draft_path(draft_id: str, kind: str) -> Path:
    if kind not in DRAFT_KINDS:
        raise InvalidDraftIdError("Некорректный тип фото")
    return draft_dir(draft_id) / f"{kind}.jpg"


def save_draft_image(draft_id: str, kind: str, upload: UploadFile) -> PhotoMeta:
    """Сохраняет фото-вход для AI-распознавания во временную папку черновика
    (не в БД и не в постоянное хранилище — см. ARCHITECTURE.md, шаг 4)."""
    image = _process_image(upload, DRAFT_MAX_DIMENSION)

    draft_dir(draft_id).mkdir(parents=True, exist_ok=True)
    full_path = resolve_draft_path(draft_id, kind)
    image.save(full_path, format="JPEG", quality=JPEG_QUALITY)

    return PhotoMeta(
        file_path=str(full_path.relative_to(_storage_root())).replace("\\", "/"),
        content_type="image/jpeg",
        file_size_bytes=full_path.stat().st_size,
        width=image.width,
        height=image.height,
    )


def read_draft_image(draft_id: str, kind: str) -> bytes | None:
    path = resolve_draft_path(draft_id, kind)
    return path.read_bytes() if path.exists() else None


def delete_draft(draft_id: str) -> None:
    shutil.rmtree(draft_dir(draft_id), ignore_errors=True)


def sweep_abandoned_drafts(older_than: timedelta = timedelta(hours=48)) -> int:
    """Удаляет папки черновиков старше `older_than` — фото были загружены,
    но запись так и не подтверждена. Возвращает число удалённых папок."""
    root = _storage_root() / DRAFT_DIR_NAME
    if not root.exists():
        return 0
    # time.time(), а не utcnow().timestamp() — naive-datetime.timestamp()
    # интерпретирует значение как local time, а не UTC, и сдвигает cutoff
    # на офсет часового пояса хоста.
    cutoff = time.time() - older_than.total_seconds()
    removed = 0
    for entry in root.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed

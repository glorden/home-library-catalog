import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from app.config import settings
from app.timeutil import utcnow

register_heif_opener()

MAX_DIMENSION = 1600
JPEG_QUALITY = 85


class InvalidImageError(Exception):
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


def save_cover_photo(copy_id: int, upload: UploadFile) -> PhotoMeta:
    """Обрабатывает и сохраняет фото обложки: применяет EXIF-ориентацию,
    затем полностью отбрасывает EXIF (в т.ч. GPS), ресайзит и сохраняет как JPEG."""
    try:
        image = Image.open(upload.file)
        image.load()
    except UnidentifiedImageError as exc:
        raise InvalidImageError("Не удалось распознать изображение") from exc

    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

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

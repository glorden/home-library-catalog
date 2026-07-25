from typing import Literal, Protocol

from pydantic import BaseModel


class ExtractionImage(BaseModel):
    kind: Literal["cover", "title_page", "title_verso", "other"]
    content: bytes
    media_type: str = "image/jpeg"


class ExtractedField(BaseModel):
    value: str | int | None
    confidence: float | None = None


class ExtractionResult(BaseModel):
    title: ExtractedField | None = None
    subtitle: ExtractedField | None = None
    authors: ExtractedField | None = None
    original_title: ExtractedField | None = None
    publisher: ExtractedField | None = None
    publication_year: ExtractedField | None = None
    publication_year_text: ExtractedField | None = None
    isbn: ExtractedField | None = None
    language: ExtractedField | None = None
    series: ExtractedField | None = None
    edition_statement: ExtractedField | None = None
    physical_description: ExtractedField | None = None
    description: ExtractedField | None = None
    provider_name: str
    model_name: str
    raw_response: str | None = None  # только для аудита, не для показа пользователю
    warnings: list[str] = []


class ExtractionService(Protocol):
    provider_name: str

    def extract(
        self, images: list[ExtractionImage], *, language_hint: str = "ru"
    ) -> ExtractionResult: ...

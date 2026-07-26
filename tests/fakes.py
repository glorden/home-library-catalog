from app.schemas.extraction import ExtractedField, ExtractionImage, ExtractionResult


class FakeExtractionService:
    """Подменяет реальный вызов Claude в тестах — CI никогда не должен ходить в сеть."""

    provider_name = "fake"
    model_name = "fake-model"

    def __init__(
        self, result: ExtractionResult | None = None, raise_error: Exception | None = None
    ):
        self._result = result
        self._raise_error = raise_error
        self.calls: list[list[ExtractionImage]] = []

    def extract(
        self, images: list[ExtractionImage], *, language_hint: str = "ru"
    ) -> ExtractionResult:
        self.calls.append(images)
        if self._raise_error is not None:
            raise self._raise_error
        return self._result or ExtractionResult(
            title=ExtractedField(value="Тестовое название", confidence=0.9),
            authors=ExtractedField(value="Тестовый автор", confidence=0.8),
            provider_name=self.provider_name,
            model_name="fake-model",
        )

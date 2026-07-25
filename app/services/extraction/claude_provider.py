import base64
import logging

import anthropic

from app.schemas.extraction import ExtractionImage, ExtractionResult
from app.services.extraction.base import (
    KIND_LABELS,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    ExtractionAuthError,
    ExtractionError,
    build_instructions,
    build_tool_parameters_schema,
    parse_tool_input,
)

logger = logging.getLogger(__name__)


def _tool_schema() -> dict:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "strict": True,
        "input_schema": build_tool_parameters_schema(),
    }


def _build_content(images: list[ExtractionImage], language_hint: str) -> list[dict]:
    content: list[dict] = []
    for image in images:
        content.append({"type": "text", "text": KIND_LABELS.get(image.kind, "Фото")})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": base64.standard_b64encode(image.content).decode("ascii"),
                },
            }
        )
    content.append({"type": "text", "text": build_instructions(language_hint)})
    return content


class ClaudeExtractionService:
    provider_name = "claude"

    def __init__(self, api_key: str, model_name: str):
        self._model_name = model_name
        self._client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

    def extract(
        self, images: list[ExtractionImage], *, language_hint: str = "ru"
    ) -> ExtractionResult:
        try:
            response = self._client.messages.create(
                model=self._model_name,
                max_tokens=4096,
                tools=[_tool_schema()],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": _build_content(images, language_hint)}],
            )
        except anthropic.AuthenticationError as exc:
            raise ExtractionAuthError("Неверный API-ключ Claude") from exc
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise ExtractionError(f"Ошибка обращения к Claude: {exc}") from exc

        usage = response.usage
        logger.info(
            "claude extraction call: model=%s input_tokens=%s output_tokens=%s stop_reason=%s",
            self._model_name,
            getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None),
            response.stop_reason,
        )

        if response.stop_reason == "refusal":
            return ExtractionResult(
                provider_name=self.provider_name,
                model_name=self._model_name,
                warnings=["Claude отказался распознавать эти фото"],
            )

        tool_block = next(
            (
                block
                for block in response.content
                if block.type == "tool_use" and block.name == TOOL_NAME
            ),
            None,
        )
        if tool_block is None:
            raise ExtractionError(
                f"Claude не вернул структурированный ответ (stop_reason={response.stop_reason})"
            )

        fields = parse_tool_input(tool_block.input)
        return ExtractionResult(
            **fields,
            provider_name=self.provider_name,
            model_name=self._model_name,
            raw_response=str(tool_block.input),
        )

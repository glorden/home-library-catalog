import base64
import json
import logging

import httpx
import openai

from app.schemas.extraction import ExtractionImage, ExtractionResult
from app.services.extraction.base import (
    EXTRACTION_HTTP_TIMEOUT_SECONDS,
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
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": TOOL_DESCRIPTION,
            "parameters": build_tool_parameters_schema(),
            "strict": True,
        },
    }


def _build_content(images: list[ExtractionImage], language_hint: str) -> list[dict]:
    content: list[dict] = []
    for image in images:
        content.append({"type": "text", "text": KIND_LABELS.get(image.kind, "Фото")})
        b64 = base64.standard_b64encode(image.content).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{image.media_type};base64,{b64}"}}
        )
    content.append({"type": "text", "text": build_instructions(language_hint)})
    return content


class OpenAICompatibleExtractionService:
    """Работает с любым сервером, отдающим OpenAI-совместимый /chat/completions
    с картинками и tool_choice на конкретную функцию — Groq, Gemini
    (её OpenAI-совместимый эндпоинт), сама OpenAI, локальные Ollama/LM Studio и т.п."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str,
        http_client: httpx.Client | None = None,
    ):
        self.model_name = model_name
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=EXTRACTION_HTTP_TIMEOUT_SECONDS,
            http_client=http_client,
        )

    def extract(
        self, images: list[ExtractionImage], *, language_hint: str = "ru"
    ) -> ExtractionResult:
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                max_tokens=4096,
                tools=[_tool_schema()],
                tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
                messages=[{"role": "user", "content": _build_content(images, language_hint)}],
            )
        except openai.AuthenticationError as exc:
            raise ExtractionAuthError("Неверный API-ключ") from exc
        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            raise ExtractionError(f"Ошибка обращения к провайдеру: {exc}") from exc

        choice = response.choices[0]
        usage = response.usage
        tokens_input = getattr(usage, "prompt_tokens", None)
        tokens_output = getattr(usage, "completion_tokens", None)
        logger.info(
            "openai-compatible extraction call: model=%s prompt_tokens=%s"
            " completion_tokens=%s finish_reason=%s",
            self.model_name,
            tokens_input,
            tokens_output,
            choice.finish_reason,
        )

        tool_calls = choice.message.tool_calls or []
        tool_call = next((call for call in tool_calls if call.function.name == TOOL_NAME), None)
        if tool_call is None:
            raise ExtractionError(
                f"Модель не вернула структурированный ответ (finish_reason={choice.finish_reason})"
            )

        try:
            tool_input = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as exc:
            raise ExtractionError("Модель вернула некорректный JSON") from exc

        fields = parse_tool_input(tool_input)
        return ExtractionResult(
            **fields,
            provider_name=self.provider_name,
            model_name=self.model_name,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            raw_response=tool_call.function.arguments,
        )

from app.schemas.extraction import ExtractedField

TOOL_NAME = "record_bibliographic_data"
TOOL_DESCRIPTION = "Записать распознанные библиографические данные книги."

# Общий таймаут обоих провайдеров — вынесен сюда, а не дублируется как
# магическое число, потому что появилась третья точка использования
# (сборка прокси-клиента в registry.py, см. DEPLOY.md, шаг 9).
EXTRACTION_HTTP_TIMEOUT_SECONDS = 90.0

# НЕ поднимать бездумно выше 4096 — проверено вживую и отменено: подъём до
# 6000 на Groq/qwen3.6-27b (лимит 8000 TPM) сразу стал давать 100%-й отказ
# `413 rate_limit_exceeded` ("Requested 9847" при вход~2727+max_tokens=6000)
# — Groq считает TPM по ЗАПРОШЕННОМУ max_tokens, а не по фактически
# использованным токенам, ещё до генерации. При этом и с 4096 модель на
# сложном реальном фото иногда обрывается на середине "рассуждения"
# переменной длины (336-1791 токенов на одном и том же тестовом фото) с
# `tool_use_failed` вместо структурированного ответа — но это существующий
# компромисс, не регрессия; поднимать это число дальше для Groq нельзя, не
# упёршись в первую ошибку. Для провайдеров с более щедрым TPM это
# ограничение не действует, но общей константой не разделяем ради одного
# провайдера без реальной необходимости.
EXTRACTION_MAX_TOKENS = 4096

# Поля Edition (кроме id/created_at/updated_at) — держать в синхроне с app/schemas/extraction.py
FIELDS: dict[str, str] = {
    "title": "Название книги, как напечатано на обложке/титуле",
    "subtitle": "Подзаголовок, если есть",
    "authors": "Автор(ы), через запятую, в том виде, как указаны на титуле",
    "original_title": "Оригинальное название, если это перевод и оно указано",
    "publisher": "Издательство",
    "publication_year": "Год издания как целое число, если указан точно",
    "publication_year_text": "Год текстом, если точная цифра неизвестна (напр. «1930-е», «б.г.»)",
    "isbn": "ISBN, если есть (в старых советских изданиях обычно отсутствует)",
    "language": "Код языка текста (ru, en и т.д.)",
    "series": "Серия, если указана",
    "edition_statement": "Сведения об издании, например «2-е изд., испр.»",
    "physical_description": "Физическое описание, например «384 с.: ил.»",
    "description": "Прочие примечания с титула/оборота, не попавшие в другие поля",
}

KIND_LABELS = {
    "cover": "Фото: обложка",
    "title_page": "Фото: титульный лист",
    "title_verso": "Фото: оборот титульного листа",
    "other": "Фото",
}

INSTRUCTIONS = """\
Это фотографии одной бумажной книги (обложка, титульный лист, оборот титула).
Извлеки библиографические данные и вызови инструмент {tool_name}.

Правила:
- Переписывай текст как он напечатан в книге, ничего не переводи.
- Если поле не удалось прочитать — верни value: null, не выдумывай.
- confidence — число от 0 до 1, насколько ты уверен в значении (null, если value: null).
- Язык текста в книге: предположительно {language_hint}, но ориентируйся на то, что видишь на фото.
"""


class ExtractionError(Exception):
    pass


class ExtractionAuthError(ExtractionError):
    pass


def build_instructions(language_hint: str) -> str:
    return INSTRUCTIONS.format(tool_name=TOOL_NAME, language_hint=language_hint)


def _extracted_field_json_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "value": {"type": ["string", "integer", "null"]},
            "confidence": {"type": ["number", "null"]},
        },
        "required": ["value", "confidence"],
        "additionalProperties": False,
    }


def build_tool_parameters_schema() -> dict:
    """JSON schema тела инструмента — общий для всех провайдеров (Claude, OpenAI-совместимые)."""
    return {
        "type": "object",
        "properties": {
            name: {**_extracted_field_json_schema(), "description": description}
            for name, description in FIELDS.items()
        },
        "required": list(FIELDS.keys()),
        "additionalProperties": False,
    }


def parse_tool_input(tool_input: dict) -> dict[str, ExtractedField]:
    return {name: ExtractedField(**tool_input[name]) for name in FIELDS}

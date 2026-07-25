from app.schemas.extraction import ExtractedField
from app.services.extraction.base import FIELDS, build_tool_parameters_schema, parse_tool_input


def test_tool_parameters_schema_requires_every_field():
    schema = build_tool_parameters_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(FIELDS)
    assert set(schema["properties"]) == set(FIELDS)


def test_parse_tool_input_handles_null_value_objects():
    # strict-режим у Claude и OpenAI-совместимых провайдеров всегда присылает
    # {"value": null, "confidence": null}, а не пропускает ключ целиком —
    # парсер должен строить ExtractedField(None, None), а не просто None.
    raw = {name: {"value": None, "confidence": None} for name in FIELDS}
    raw["title"] = {"value": "Название", "confidence": 0.8}

    parsed = parse_tool_input(raw)

    assert parsed["title"] == ExtractedField(value="Название", confidence=0.8)
    assert parsed["isbn"] == ExtractedField(value=None, confidence=None)
    assert set(parsed) == set(FIELDS)

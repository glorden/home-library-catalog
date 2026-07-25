from app.services.extraction.base import TOOL_NAME
from app.services.extraction.claude_provider import _tool_schema


def test_tool_schema_uses_claude_input_schema_shape():
    schema = _tool_schema()
    assert schema["name"] == TOOL_NAME
    assert schema["strict"] is True
    assert schema["input_schema"]["additionalProperties"] is False
    assert schema["input_schema"]["type"] == "object"

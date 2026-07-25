from app.services.extraction.base import TOOL_NAME
from app.services.extraction.openai_compatible_provider import _tool_schema


def test_tool_schema_uses_openai_function_shape():
    schema = _tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == TOOL_NAME
    assert schema["function"]["strict"] is True
    assert schema["function"]["parameters"]["additionalProperties"] is False
    assert schema["function"]["parameters"]["type"] == "object"

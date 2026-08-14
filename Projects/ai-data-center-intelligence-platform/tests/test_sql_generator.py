import json
from types import SimpleNamespace

import pytest

from src.sql_generator import OpenAISQLGenerator, VerifiedExampleSQLGenerator


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text=json.dumps({"sql": "SELECT facility_id FROM facilities LIMIT 5"}),
            usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        )


def test_openai_generator_uses_strict_structured_output():
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    result = OpenAISQLGenerator("test-key", "gpt-5.4-mini", client).generate(
        "List facilities", "facilities(facility_id)"
    )

    assert result.source == "openai"
    assert result.input_tokens == 12
    assert result.sql.startswith("SELECT")
    assert responses.kwargs["text"]["format"]["strict"] is True
    assert responses.kwargs["text"]["format"]["schema"]["additionalProperties"] is False


def test_openai_generator_requires_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAISQLGenerator("", "gpt-5.4-mini", SimpleNamespace())


def test_offline_generator_error_mentions_openai():
    with pytest.raises(RuntimeError, match="OpenAI"):
        VerifiedExampleSQLGenerator().generate("an unsupported question")

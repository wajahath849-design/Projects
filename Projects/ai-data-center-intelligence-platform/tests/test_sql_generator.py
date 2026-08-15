import json
from types import SimpleNamespace

import pytest

from src.sql_generator import OllamaSQLGenerator, VerifiedExampleSQLGenerator


class FakeOllamaClient:
    def __init__(self):
        self.kwargs = None

    def chat(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            message=SimpleNamespace(content=json.dumps({"sql": "SELECT facility_id FROM facilities LIMIT 5"})),
            prompt_eval_count=12,
            eval_count=8,
        )


def test_ollama_generator_uses_structured_output():
    client = FakeOllamaClient()
    result = OllamaSQLGenerator("http://localhost:11434", "qwen2.5-coder:7b", client).generate(
        "List facilities", "facilities(facility_id)"
    )

    assert result.source == "ollama"
    assert result.input_tokens == 12
    assert result.output_tokens == 8
    assert result.sql.startswith("SELECT")
    assert client.kwargs["format"]["additionalProperties"] is False
    assert client.kwargs["options"]["temperature"] == 0


def test_offline_generator_error_mentions_ollama():
    with pytest.raises(RuntimeError, match="Ollama"):
        VerifiedExampleSQLGenerator().generate("an unsupported question")


def test_unreachable_ollama_server_is_detected():
    assert not OllamaSQLGenerator.server_available("http://127.0.0.1:1", timeout=0.05)

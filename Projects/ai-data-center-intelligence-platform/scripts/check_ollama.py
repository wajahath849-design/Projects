from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.sql_generator import OllamaSQLGenerator


def main() -> None:
    server = OllamaSQLGenerator.server_available(settings.ollama_host, timeout=2)
    model = server and OllamaSQLGenerator.model_available(
        settings.ollama_host, settings.ollama_model, timeout=2
    )
    print(f"Ollama server: {'ready' if server else 'not reachable'}")
    print(f"Configured model: {settings.ollama_model}")
    print(f"Model status: {'ready' if model else 'not installed or unavailable'}")
    if not server:
        raise SystemExit("Start Ollama, then run this check again.")
    if not model:
        raise SystemExit(f"Run: ollama pull {settings.ollama_model}")


if __name__ == "__main__":
    main()

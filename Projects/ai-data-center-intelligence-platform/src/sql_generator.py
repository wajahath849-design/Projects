from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from src.untrusted_content import untrusted_data_rules, wrap_untrusted_text


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str
    source: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_duration_ms: float | None = None
    load_duration_ms: float | None = None


class OllamaSQLGenerator:
    """Generate SQL locally with a persistent Ollama model and strict JSON output."""

    def __init__(
        self,
        host: str,
        model: str,
        client=None,
        *,
        keep_alive: str = "30m",
        num_ctx: int = 4096,
        max_tokens: int = 256,
        timeout_seconds: float = 180,
    ) -> None:
        if client is None:
            try:
                from ollama import Client
            except ImportError as error:
                raise RuntimeError("Install the official ollama Python package") from error
            client = Client(host=host, timeout=timeout_seconds)
        self.client = client
        self.host = host.rstrip("/")
        self.model = model
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens

    @staticmethod
    def server_available(host: str, timeout: float = 0.5) -> bool:
        try:
            with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=timeout) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    @staticmethod
    def model_available(host: str, model: str, timeout: float = 0.5) -> bool:
        try:
            with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            names = {item.get("name") for item in payload.get("models", [])}
            return model in names or (":" not in model and f"{model}:latest" in names)
        except (OSError, ValueError, urllib.error.URLError):
            return False

    @staticmethod
    def build_prompt(question: str, context: str) -> str:
        return f"""Write one read-only SQLite SELECT for QUESTION using exact table and column names from CONTEXT.
{untrusted_data_rules()}
Forbidden: PRAGMA, ATTACH, DDL, DML, comments, multiple statements.
Return human-readable labels; use half-open date ranges for calendar years.
Output must match the supplied JSON schema.

RETRIEVED CONTEXT
{wrap_untrusted_text(context, "retrieved_sql_context")}

USER QUESTION
{wrap_untrusted_text(question, "user_question", max_chars=4_000)}"""

    @staticmethod
    def _duration_ms(response, name: str) -> float | None:
        value = getattr(response, name, None)
        if value is None and isinstance(response, dict):
            value = response.get(name)
        return round(value / 1_000_000, 3) if value is not None else None

    def generate(self, question: str, context: str) -> GeneratedSQL:
        schema = {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
            "additionalProperties": False,
        }
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": self.build_prompt(question, context)}],
            format=schema,
            keep_alive=self.keep_alive,
            options={
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": self.max_tokens,
            },
        )
        message = getattr(response, "message", None)
        content = (
            getattr(message, "content", None)
            if message is not None
            else response["message"]["content"]
        )
        sql = json.loads(content)["sql"]
        return GeneratedSQL(
            sql,
            "ollama",
            getattr(response, "prompt_eval_count", None),
            getattr(response, "eval_count", None),
            self._duration_ms(response, "total_duration"),
            self._duration_ms(response, "load_duration"),
        )


class VerifiedExampleSQLGenerator:
    """Small offline route for demonstrations and tests; not a general NL-to-SQL model."""

    EXAMPLES = {
        "highest average pue in 2020": """SELECT f.facility_name, AVG(p.pue) AS average_pue FROM power_metrics p JOIN facilities f ON f.facility_id=p.facility_id WHERE p.timestamp >= '2020-01-01' AND p.timestamp < '2021-01-01' GROUP BY f.facility_name ORDER BY average_pue DESC LIMIT 1""",
        "most downtime per server": """SELECT facility_name, downtime_minutes_per_server FROM vw_facility_reliability ORDER BY downtime_minutes_per_server DESC LIMIT 1""",
        "cooling costs change between 2017 and 2025": """SELECT substr(timestamp,1,4) AS year, SUM(cooling_cost) AS total_cooling_cost FROM power_metrics WHERE timestamp >= '2017-01-01' AND timestamp < '2026-01-01' GROUP BY year ORDER BY year""",
    }

    def generate(self, question: str, context: str = "") -> GeneratedSQL:
        lower = question.lower()
        for key, sql in self.EXAMPLES.items():
            if key in lower:
                return GeneratedSQL(sql, "verified_example")
        raise RuntimeError("No offline verified SQL example matches; start Ollama for general questions")

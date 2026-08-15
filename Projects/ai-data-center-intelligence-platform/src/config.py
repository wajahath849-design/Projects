from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    database_path: Path = PROJECT_ROOT / os.getenv("DATABASE_PATH", "database/datacenter.db")
    contract_path: Path = PROJECT_ROOT / "analytics/canonical_data_contract.json"
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    max_result_rows: int = int(os.getenv("MAX_RESULT_ROWS", "1000"))
    sql_timeout_seconds: float = float(os.getenv("SQL_TIMEOUT_SECONDS", "5"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "6"))


settings = Settings()

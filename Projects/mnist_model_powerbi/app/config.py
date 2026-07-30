from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(BASE / ".env")

INCOMING = BASE / "data" / "incoming"
PROCESSED = BASE / "data" / "processed"
FAILED = BASE / "data" / "failed"
LOG_FILE = BASE / "logs" / "watcher.log"
MODEL_CONFIG = BASE / "config" / "models.yml"

for folder in (INCOMING, PROCESSED, FAILED, LOG_FILE.parent):
    folder.mkdir(parents=True, exist_ok=True)

DB_SERVER = os.getenv("DB_SERVER", r"localhost\SQLEXPRESS")
DB_NAME = os.getenv("DB_NAME", "AIModelAnalytics")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
MAX_RETAINED_IMAGES = max(1, int(os.getenv("MAX_RETAINED_IMAGES", "20")))
IMAGE_RETENTION_GRACE_SECONDS = max(
    0, int(os.getenv("IMAGE_RETENTION_GRACE_SECONDS", "300"))
)
STABLE_FILE_TIMEOUT_SECONDS = float(os.getenv("STABLE_FILE_TIMEOUT_SECONDS", "30"))
PIPELINE_VERSION = os.getenv("PIPELINE_VERSION", "2.0.0").strip() or "2.0.0"

"""JSON logs without credentials or raw business payloads."""
import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        result = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                  "logger": record.name, "message": record.getMessage()}
        for key in ("run_id", "workflow_name", "status", "rows_processed"):
            if hasattr(record, key):
                result[key] = getattr(record, key)
        return json.dumps(result)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)

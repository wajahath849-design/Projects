from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def log_event(path: Path | str, **fields) -> None:
    safe = {key: value for key, value in fields.items() if "key" not in key.lower() and "secret" not in key.lower()}
    safe["timestamp"] = datetime.now(timezone.utc).isoformat()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(safe, default=str) + "\n")

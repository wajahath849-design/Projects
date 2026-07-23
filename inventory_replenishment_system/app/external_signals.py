from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session


class ExternalSignalError(RuntimeError):
    pass


def _read_json_path(payload: Any, dotted_path: str) -> Any:
    current = payload
    for part in dotted_path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ExternalSignalError(f"Cannot resolve JSON path at {part}")
    return current


def ingest_external_signal(
    session: Session,
    *,
    url: str,
    allowed_hosts: list[str],
    region: str,
    signal_type: str,
    value_path: str,
    source_name: str,
    signal_date: date | None = None,
    headers: dict[str, str] | None = None,
    scale: float = 1.0,
    offset: float = 0.0,
    min_value: float | None = None,
    max_value: float | None = None,
) -> dict[str, Any]:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https":
        raise ExternalSignalError("External signal URLs must use HTTPS")
    if parsed_url.hostname not in set(allowed_hosts):
        raise ExternalSignalError(f"Host is not allow-listed: {parsed_url.hostname}")

    response = requests.get(url, headers=headers or {}, timeout=(5, 20))
    response.raise_for_status()
    payload = response.json()
    raw_value = float(_read_json_path(payload, value_path))
    value = raw_value * scale + offset
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    signal_date = signal_date or date.today()

    session.execute(
        text(
            """
            INSERT INTO inventory.external_signals
                (signal_date, region, signal_type, signal_value, source_name, source_reference)
            VALUES
                (:signal_date, :region, :signal_type, :signal_value, :source_name, :source_reference)
            ON CONFLICT (signal_date, region, signal_type, source_name) DO UPDATE SET
                signal_value = EXCLUDED.signal_value,
                source_reference = EXCLUDED.source_reference,
                ingested_at = CURRENT_TIMESTAMP
            """
        ),
        {
            "signal_date": signal_date,
            "region": region,
            "signal_type": signal_type,
            "signal_value": value,
            "source_name": source_name,
            "source_reference": url,
        },
    )
    session.commit()
    return {
        "signal_date": signal_date.isoformat(),
        "region": region,
        "signal_type": signal_type,
        "raw_value": raw_value,
        "signal_value": value,
        "source_name": source_name,
    }

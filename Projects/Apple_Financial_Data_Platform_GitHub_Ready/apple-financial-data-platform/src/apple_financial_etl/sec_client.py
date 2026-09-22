from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .config import Settings

LOGGER = logging.getLogger(__name__)


class SecClientError(RuntimeError):
    pass


class SecClient:
    BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    def __init__(self, settings: Settings) -> None:
        settings.validate_sec_user_agent()
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.sec_user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            }
        )

    def _cache_path(self) -> Path:
        cik = self.settings.sec_cik.zfill(10)
        return self.settings.raw_data_dir / f"companyfacts_CIK{cik}.json"

    def _cache_is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        cache_age = datetime.now(timezone.utc) - modified
        return cache_age < timedelta(hours=self.settings.sec_cache_hours)

    def _download(self) -> dict[str, Any]:
        url = self.BASE_URL.format(cik=self.settings.sec_cik.zfill(10))
        LOGGER.info("Downloading SEC Company Facts from %s", url)
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.session.get(
                    url, timeout=self.settings.sec_request_timeout_seconds
                )
                if response.status_code == 429:
                    raise SecClientError("SEC rate limit response received (HTTP 429).")
                if response.status_code >= 500:
                    raise SecClientError(
                        f"SEC temporary server error: HTTP {response.status_code}"
                    )
                response.raise_for_status()
                payload = response.json()
                if payload.get("cik") is None or "facts" not in payload:
                    raise SecClientError(
                        "SEC response did not contain the expected Company Facts structure."
                    )
                return payload
            except (requests.RequestException, SecClientError) as exc:
                last_error = exc
                if attempt == 3:
                    break
                delay_seconds = min(2**attempt, 8)
                LOGGER.warning(
                    "SEC request failed (%s). Retrying after %s seconds.",
                    exc,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
        raise SecClientError(f"SEC download failed after retries: {last_error}")

    def get_company_facts(self, force_refresh: bool = False) -> dict[str, Any]:
        cache_path = self._cache_path()
        if not force_refresh and self._cache_is_fresh(cache_path):
            LOGGER.info("Using cached SEC response: %s", cache_path)
            return json.loads(cache_path.read_text(encoding="utf-8"))

        payload = self._download()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.info("Saved raw SEC response to %s", cache_path)
        return payload

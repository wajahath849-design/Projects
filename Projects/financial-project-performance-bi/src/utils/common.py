from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def settings() -> dict:
    return json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))


def path_from_config(key: str) -> Path:
    return ROOT / settings()[key]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def month_start(value) -> pd.Timestamp:
    return pd.Timestamp(value).to_period("M").to_timestamp()


def date_key(value) -> int:
    return int(pd.Timestamp(value).strftime("%Y%m%d"))


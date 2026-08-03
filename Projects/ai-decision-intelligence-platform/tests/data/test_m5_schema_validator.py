"""Unit tests for critical M5 validation rules."""

from pathlib import Path

import pandas as pd
import pytest

from decision_intelligence.ingestion.schema_validator import (
    M5ValidationError,
    validate_calendar,
    validate_file_set,
    validate_headers,
    validate_prices_chunk,
    validate_sales_chunk,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_ROOT / "data" / "samples" / "m5"


def test_generated_sample_has_valid_files_headers_and_calendar() -> None:
    paths = validate_file_set(SAMPLE_DIR)
    headers = validate_headers(paths)
    calendar = validate_calendar(paths["calendar.csv"])
    assert len(calendar) == 28
    assert "d_28" in headers["sales_train_validation.csv"]


def test_missing_file_set_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(M5ValidationError, match="Missing required M5 files"):
        validate_file_set(tmp_path)


def test_negative_sales_are_rejected() -> None:
    chunk = pd.DataFrame(
        [
            {
                "id": "x",
                "item_id": "i",
                "dept_id": "d",
                "cat_id": "c",
                "store_id": "s",
                "state_id": "CA",
                "d_1": -1,
            }
        ]
    )
    with pytest.raises(M5ValidationError, match="cannot be negative"):
        validate_sales_chunk(chunk, ["d_1"])


def test_duplicate_price_business_records_are_rejected() -> None:
    chunk = pd.DataFrame(
        [
            {"store_id": "s", "item_id": "i", "wm_yr_wk": 1, "sell_price": 1.0},
            {"store_id": "s", "item_id": "i", "wm_yr_wk": 1, "sell_price": 1.0},
        ]
    )
    with pytest.raises(M5ValidationError, match="duplicate business records"):
        validate_prices_chunk(chunk)

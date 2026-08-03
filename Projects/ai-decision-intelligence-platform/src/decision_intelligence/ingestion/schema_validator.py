"""M5 file existence, schema, type, range, and identifier validation."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)
DAY_COLUMN_PATTERN = re.compile(r"^d_([1-9]\d*)$")
REQUIRED_COLUMNS = {
    "calendar.csv": {
        "date",
        "wm_yr_wk",
        "weekday",
        "wday",
        "month",
        "year",
        "d",
        "event_name_1",
        "event_type_1",
        "snap_CA",
        "snap_TX",
        "snap_WI",
    },
    "sales_train_validation.csv": {
        "id",
        "item_id",
        "dept_id",
        "cat_id",
        "store_id",
        "state_id",
    },
    "sell_prices.csv": {"store_id", "item_id", "wm_yr_wk", "sell_price"},
}


class M5ValidationError(ValueError):
    """Raised when an M5 input fails a critical validation rule."""


@dataclass(frozen=True)
class FileValidation:
    """Validated metadata for one input file."""

    name: str
    columns: tuple[str, ...]
    row_count: int


def _read_header(path: Path) -> list[str]:
    try:
        return list(pd.read_csv(path, nrows=0).columns)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise M5ValidationError(f"Unable to read {path.name}: {exc}") from exc


def validate_file_set(directory: Path) -> dict[str, Path]:
    """Confirm that exactly the required named M5 inputs are available."""
    paths = {name: directory / name for name in REQUIRED_COLUMNS}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise M5ValidationError(
            f"Missing required M5 files in {directory}: {', '.join(sorted(missing))}"
        )
    return paths


def validate_headers(paths: dict[str, Path]) -> dict[str, tuple[str, ...]]:
    """Validate required columns and ordered contiguous sales day columns."""
    headers: dict[str, tuple[str, ...]] = {}
    for name, path in paths.items():
        columns = _read_header(path)
        missing = REQUIRED_COLUMNS[name] - set(columns)
        if missing:
            raise M5ValidationError(f"{name} is missing columns: {sorted(missing)}")
        if len(columns) != len(set(columns)):
            raise M5ValidationError(f"{name} contains duplicate column names")
        headers[name] = tuple(columns)
    day_numbers = [
        int(match.group(1))
        for column in headers["sales_train_validation.csv"]
        if (match := DAY_COLUMN_PATTERN.match(column))
    ]
    if not day_numbers:
        raise M5ValidationError("sales_train_validation.csv contains no d_* demand columns")
    if day_numbers != list(range(day_numbers[0], day_numbers[-1] + 1)):
        raise M5ValidationError("Sales demand day columns must be ordered and contiguous")
    return headers


def validate_calendar(path: Path) -> pd.DataFrame:
    """Load the small calendar table and validate dates, keys, and date range."""
    try:
        calendar = pd.read_csv(path, parse_dates=["date"])
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        raise M5ValidationError(f"Invalid calendar.csv: {exc}") from exc
    if calendar.empty or calendar["date"].isna().any():
        raise M5ValidationError("calendar.csv must contain valid dates")
    if calendar["d"].duplicated().any() or calendar["date"].duplicated().any():
        raise M5ValidationError("calendar.csv contains duplicate day or date identifiers")
    if not calendar["date"].is_monotonic_increasing:
        raise M5ValidationError("calendar.csv dates must be increasing")
    if calendar["date"].min().year < 2011 or calendar["date"].max().year > 2030:
        raise M5ValidationError("calendar.csv date range is outside the expected M5 range")
    return calendar


def validate_sales_chunk(chunk: pd.DataFrame, day_columns: list[str]) -> None:
    """Reject missing identifiers, duplicates, nonnumeric demand, or negative demand."""
    identifiers = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    if chunk[identifiers].isna().any().any():
        raise M5ValidationError("Sales identifiers cannot be missing")
    if chunk["id"].duplicated().any():
        raise M5ValidationError("Sales chunk contains duplicate id values")
    numeric = chunk[day_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        raise M5ValidationError("Sales demand columns must be numeric and non-null")
    if (numeric < 0).any().any():
        raise M5ValidationError("Sales demand cannot be negative")


def validate_prices_chunk(chunk: pd.DataFrame) -> None:
    """Reject invalid weekly price records."""
    required = ["store_id", "item_id", "wm_yr_wk", "sell_price"]
    if chunk[required].isna().any().any():
        raise M5ValidationError("Price fields cannot be missing")
    prices = pd.to_numeric(chunk["sell_price"], errors="coerce")
    if prices.isna().any() or (prices < 0).any():
        raise M5ValidationError("Sell prices must be non-negative numbers")
    if chunk.duplicated(["store_id", "item_id", "wm_yr_wk"]).any():
        raise M5ValidationError("Price chunk contains duplicate business records")

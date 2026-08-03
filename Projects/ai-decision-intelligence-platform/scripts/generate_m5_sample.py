"""Generate reproducible, synthetic M5-shaped CSV files for local testing."""

from __future__ import annotations

import argparse
import logging
import random
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def _week_id(value: date) -> int:
    iso = value.isocalendar()
    return iso.year * 100 + iso.week


def generate_sample(output_directory: Path, seed: int, days: int = 28) -> dict[str, int]:
    """Write deterministic sample files and return their source row counts."""
    if days < 7:
        raise ValueError("Sample must contain at least seven days")
    rng = random.Random(seed)
    output_directory.mkdir(parents=True, exist_ok=True)
    start = date(2016, 1, 1)
    calendar_rows: list[dict[str, object]] = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        calendar_rows.append(
            {
                "date": current.isoformat(),
                "wm_yr_wk": _week_id(current),
                "weekday": current.strftime("%A"),
                "wday": current.isoweekday(),
                "month": current.month,
                "year": current.year,
                "d": f"d_{offset + 1}",
                "event_name_1": "SyntheticPromotion" if offset == 14 else None,
                "event_type_1": "Cultural" if offset == 14 else None,
                "event_name_2": None,
                "event_type_2": None,
                "snap_CA": int(current.day % 3 == 0),
                "snap_TX": int(current.day % 4 == 0),
                "snap_WI": int(current.day % 5 == 0),
            }
        )
    products = [
        ("SAMPLE_ITEM_001", "SAMPLE_FOODS_1", "SAMPLE_FOODS", 3.99),
        ("SAMPLE_ITEM_002", "SAMPLE_FOODS_1", "SAMPLE_FOODS", 5.49),
        ("SAMPLE_ITEM_003", "SAMPLE_HOUSEHOLD_1", "SAMPLE_HOUSEHOLD", 8.99),
        ("SAMPLE_ITEM_004", "SAMPLE_HOBBIES_1", "SAMPLE_HOBBIES", 6.75),
    ]
    stores = [("SAMPLE_CA_1", "CA"), ("SAMPLE_TX_1", "TX")]
    sales_rows: list[dict[str, object]] = []
    for product_index, (item, department, category, _) in enumerate(products):
        for store_index, (store, state) in enumerate(stores):
            row: dict[str, object] = {
                "id": f"{item}_{store}_validation",
                "item_id": item,
                "dept_id": department,
                "cat_id": category,
                "store_id": store,
                "state_id": state,
            }
            base = 2 + product_index + store_index
            for offset in range(days):
                current = start + timedelta(days=offset)
                weekend_uplift = 2 if current.weekday() >= 5 else 0
                promotion_uplift = 3 if offset == 14 else 0
                row[f"d_{offset + 1}"] = max(
                    0, base + weekend_uplift + promotion_uplift + rng.randint(-2, 2)
                )
            sales_rows.append(row)
    price_rows: list[dict[str, object]] = []
    weeks = sorted({_week_id(start + timedelta(days=offset)) for offset in range(days)})
    for item, _, _, base_price in products:
        for store, _ in stores:
            for week_index, week in enumerate(weeks):
                price_rows.append(
                    {
                        "store_id": store,
                        "item_id": item,
                        "wm_yr_wk": week,
                        "sell_price": round(base_price * (1 + 0.01 * week_index), 2),
                    }
                )
    pd.DataFrame(calendar_rows).to_csv(output_directory / "calendar.csv", index=False)
    pd.DataFrame(sales_rows).to_csv(output_directory / "sales_train_validation.csv", index=False)
    pd.DataFrame(price_rows).to_csv(output_directory / "sell_prices.csv", index=False)
    return {
        "calendar": len(calendar_rows),
        "sales_series": len(sales_rows),
        "prices": len(price_rows),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the sample and report stable row counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "samples" / "m5")
    parser.add_argument("--days", type=int, default=28)
    args = parser.parse_args(argv)
    try:
        app, _ = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        counts = generate_sample(args.output, app.random_seed, args.days)
        for name, count in counts.items():
            print(f"{name}_rows={count}")
        print("SYNTHETIC M5 SAMPLE GENERATED")
        return 0
    except (OSError, ValueError) as exc:
        LOGGER.exception("Sample generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

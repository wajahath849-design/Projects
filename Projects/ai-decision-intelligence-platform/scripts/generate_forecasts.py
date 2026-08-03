"""Generate and persist Phase 10 multi-horizon forecasts."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.forecasting.forecast_generator import generate_forecasts  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> int:
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        output = PROJECT_ROOT / "data" / "exports" / "forecasts"
        result = generate_forecasts(
            database,
            PROJECT_ROOT / "data" / "processed" / "features" / "sample_features.parquet",
            PROJECT_ROOT / "models" / "metadata" / "selected_model.json",
            output,
        )
        print(f"forecast_rows={len(result)}")
        print(f"series={result[['product_id', 'store_id']].drop_duplicates().shape[0]}")
        print(f"horizon_labels={sorted(result['horizon_days'].unique())}")
        print("FORECAST GENERATION PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Forecast generation failed: %s", exc)
        print("FORECAST GENERATION FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

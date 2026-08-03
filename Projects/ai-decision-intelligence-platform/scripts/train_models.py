"""Train, evaluate, persist, and select all Phase 6-9 forecasting models."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.forecasting.model_selection import train_compare_select  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features", type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "features" / "sample_features.parquet",
    )
    args = parser.parse_args(argv)
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        comparison, selected = train_compare_select(
            database, args.features, PROJECT_ROOT, app.random_seed
        )
        columns = ["model_id", "wape", "rmse", "mae", "smape", "bias", "selection_score"]
        print(comparison[columns].to_string(index=False))
        print(f"selected_model={selected['model_id']}")
        print("MODEL TRAINING AND SELECTION PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Model training failed: %s", exc)
        print("MODEL TRAINING AND SELECTION FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

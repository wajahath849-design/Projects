"""Build the Phase 5 leakage-safe Parquet feature dataset."""

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

from decision_intelligence.features.feature_pipeline import build_feature_dataset  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Build features and report row, column, and usable training counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Use manually loaded M5 data")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "features" / "sample_features.parquet",
    )
    args = parser.parse_args(argv)
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        source = "M5" if args.full else "SYNTHETIC_M5_SAMPLE"
        frame = build_feature_dataset(database, args.output, source)
        usable = frame[["lag_1", "lag_7", "lag_14", "rolling_mean_7"]].notna().all(axis=1).sum()
        print(f"feature_rows={len(frame)}")
        print(f"feature_columns={len(frame.columns)}")
        print(f"model_usable_rows={usable}")
        print("FEATURE BUILD PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Feature build failed: %s", exc)
        print("FEATURE BUILD FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

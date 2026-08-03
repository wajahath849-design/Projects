"""Generate and persist Phase 10 ranked forecast explanations."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.explainability import generate_explanations  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> int:
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        result = generate_explanations(
            database,
            PROJECT_ROOT / "data" / "exports" / "forecasts" / "forecast_detail.parquet",
            PROJECT_ROOT / "models" / "metadata" / "selected_model.json",
            PROJECT_ROOT / "data" / "exports" / "forecasts" / "forecast_explanations.parquet",
        )
        print(f"explanation_rows={len(result)}")
        print(f"method={result['explanation_method'].iloc[0]}")
        print("EXPLANATION GENERATION PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Explanation generation failed: %s", exc)
        print("EXPLANATION GENERATION FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

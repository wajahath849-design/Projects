"""Run and persist all Phase 13 business scenarios."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.scenarios import run_all_scenarios  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> int:
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        result = run_all_scenarios(
            database, app.config_dir / "scenarios.yaml",
            PROJECT_ROOT / "data" / "exports" / "scenarios",
        )
        print(f"scenario_types={result['scenario_id'].nunique()}")
        print(f"scenario_result_rows={len(result)}")
        print("SCENARIO SIMULATION PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Scenario simulation failed: %s", exc)
        print("SCENARIO SIMULATION FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

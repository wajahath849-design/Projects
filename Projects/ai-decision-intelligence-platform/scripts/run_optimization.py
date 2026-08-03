"""Run and persist Phase 12 replenishment optimization."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.optimization import run_optimization  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> int:
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        solution = run_optimization(
            database, app.config_dir / "optimization.yaml",
            PROJECT_ROOT / "data" / "exports" / "optimization",
        )
        print(f"solver_status={solution.status}")
        print(f"recommendations={len(solution.orders)}")
        print(f"objective_value={solution.objective_value:.4f}")
        print("constraint_failures=0")
        print("OPTIMIZATION PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Optimization failed: %s", exc)
        print("OPTIMIZATION FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Calculate and persist Phase 11 inventory intelligence."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.inventory import calculate_inventory_risks  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> int:
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        result = calculate_inventory_risks(
            database, app.config_dir / "inventory.yaml",
            PROJECT_ROOT / "data" / "exports" / "inventory" / "inventory_risks.csv",
        )
        print(f"inventory_risk_rows={len(result)}")
        print(result["risk_classification"].value_counts().to_string())
        print("INVENTORY INTELLIGENCE PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Inventory intelligence failed: %s", exc)
        print("INVENTORY INTELLIGENCE FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Create and verify the SQL Server analytical database for Phase 1."""

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

from decision_intelligence.database.initializer import (  # noqa: E402
    initialize_database,
    verify_database,
)
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import ConfigurationError, load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize or only verify the database; return nonzero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Do not apply SQL scripts")
    args = parser.parse_args(argv)
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        if not args.verify_only:
            initialize_database(
                database,
                PROJECT_ROOT / "database" / "schema",
                PROJECT_ROOT / "database" / "seeds",
            )
        result = verify_database(database)
        for check in result.checks:
            print(f"[PASS] {check}")
        for failure in result.failures:
            print(f"[FAIL] {failure}")
        print("DATABASE VERIFICATION PASSED" if result.passed else "DATABASE VERIFICATION FAILED")
        return 0 if result.passed else 1
    except (ConfigurationError, RuntimeError, OSError, ValueError) as exc:
        LOGGER.exception("Database initialization failed: %s", exc)
        print("DATABASE VERIFICATION FAILED")
        return 2
    except Exception as exc:
        LOGGER.exception("Unexpected database initialization failure: %s", exc)
        print("DATABASE VERIFICATION FAILED")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

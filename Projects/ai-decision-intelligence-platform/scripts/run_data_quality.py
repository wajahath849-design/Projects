"""Run all data-quality checks, persist results, and write local reports."""

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

from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.quality.data_quality import run_data_quality  # noqa: E402
from decision_intelligence.quality.quality_report import write_quality_reports  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute quality checks and return nonzero when the critical gate fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=PROJECT_ROOT / "reports" / "data_quality",
    )
    args = parser.parse_args(argv)
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        report = run_data_quality(database)
        paths = write_quality_reports(report, args.output_directory)
        for result in report.results:
            print(
                f"[{result.status}] {result.check_name}: "
                f"checked={result.records_checked}, failed={result.failed_records}"
            )
        for format_name, path in paths.items():
            print(f"{format_name}_report={path}")
        if report.passed:
            print("DATA QUALITY GATE PASSED")
            return 0
        print("DATA QUALITY GATE FAILED")
        return 1
    except Exception as exc:
        LOGGER.exception("Data-quality execution failed: %s", exc)
        print("DATA QUALITY EXECUTION ERROR")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

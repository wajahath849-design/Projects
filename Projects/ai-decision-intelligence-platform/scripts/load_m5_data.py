"""Validate and load M5 CSV files into SQL Server in bounded chunks."""

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

from decision_intelligence.ingestion.m5_loader import (  # noqa: E402
    IngestionConfig,
    M5IngestionPipeline,
)
from decision_intelligence.ingestion.schema_validator import M5ValidationError  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import (  # noqa: E402
    ConfigurationError,
    load_settings,
    load_yaml,
)

LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Load sample or manually downloaded M5 files and return a stable exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", action="store_true", help="Load generated synthetic sample files"
    )
    parser.add_argument(
        "--data-directory", type=Path, help="Override the configured input directory"
    )
    parser.add_argument("--chunk-size", type=int, help="Override CSV rows per chunk")
    args = parser.parse_args(argv)
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        root = load_yaml(app.config_dir / "ingestion.yaml").get("ingestion")
        if not isinstance(root, dict):
            raise ConfigurationError("ingestion.yaml requires an ingestion mapping")
        configured = root["sample_directory"] if args.sample else root["raw_directory"]
        data_directory = (args.data_directory or PROJECT_ROOT / str(configured)).resolve()
        source = "SYNTHETIC_M5_SAMPLE" if args.sample else "M5"
        version = "sample-v1" if args.sample else "validation"
        config = IngestionConfig(
            data_directory=data_directory,
            chunk_size=args.chunk_size or int(root["chunk_size"]),
            database_batch_size=int(root["database_batch_size"]),
            source_system=source,
            data_version=version,
        )
        result = M5IngestionPipeline(database, config).run()
        print(f"pipeline_run_id={result.pipeline_run_id}")
        print(f"calendar_rows={result.calendar_rows}")
        print(f"sales_series_rows={result.sales_series_rows}")
        print(f"sales_fact_rows_processed={result.sales_fact_rows}")
        print(f"price_source_rows={result.price_source_rows}")
        print(f"price_fact_rows_processed={result.price_fact_rows}")
        print(f"database_sales_rows={result.database_sales_rows}")
        print(f"database_price_rows={result.database_price_rows}")
        if result.database_sales_rows != result.sales_fact_rows:
            raise RuntimeError("Database sales count does not match the processed sample grain")
        if result.database_price_rows != result.price_fact_rows:
            raise RuntimeError("Database price count does not match the processed sample grain")
        print("M5 INGESTION PASSED")
        return 0
    except (ConfigurationError, M5ValidationError, RuntimeError, OSError, ValueError) as exc:
        LOGGER.exception("M5 ingestion failed: %s", exc)
        print("M5 INGESTION FAILED")
        return 1
    except Exception as exc:
        LOGGER.exception("Unexpected M5 ingestion failure: %s", exc)
        print("M5 INGESTION FAILED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

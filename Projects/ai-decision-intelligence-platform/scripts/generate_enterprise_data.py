"""Generate, validate, export, and load reproducible synthetic enterprise data."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.database.connection import connect, fetch_scalar  # noqa: E402
from decision_intelligence.generation.enterprise_generator import (  # noqa: E402
    EnterpriseData,
    EnterpriseGenerator,
)
from decision_intelligence.generation.enterprise_loader import (  # noqa: E402
    apply_enterprise_migration,
    load_enterprise_data,
)
from decision_intelligence.generation.validation import validate_enterprise_data  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings, load_yaml  # noqa: E402

LOGGER = logging.getLogger(__name__)


def _fetch_frame(connection: object, query: str, parameters: tuple[object, ...]) -> pd.DataFrame:
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute(query, parameters)
    columns = [description[0] for description in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)


def _load_generation_inputs(
    database_settings: object,
    source_system: str,
    product_limit: int,
) -> tuple[pd.DataFrame, list[str], pd.DataFrame, list[int]]:
    with connect(database_settings) as connection:  # type: ignore[arg-type]
        products = _fetch_frame(
            connection,
            """SELECT TOP (?) p.ProductID AS product_id
            FROM dbo.DimProduct p
            WHERE EXISTS (SELECT 1 FROM dbo.FactSales s
              WHERE s.ProductKey=p.ProductKey AND s.SourceSystem=?)
            ORDER BY p.ProductID""",
            (product_limit, source_system),
        )
        if products.empty:
            raise RuntimeError(f"No products found for source {source_system}; run Phase 2 first")
        product_ids = list(products["product_id"].astype(str))
        placeholders = ",".join("?" for _ in product_ids)
        sales = _fetch_frame(
            connection,
            f"""SELECT p.ProductID AS product_id,s.DateKey AS date_key,
              SUM(CAST(s.Quantity AS int)) AS demand
            FROM dbo.FactSales s JOIN dbo.DimProduct p ON p.ProductKey=s.ProductKey
            WHERE s.SourceSystem=? AND p.ProductID IN ({placeholders})
            GROUP BY p.ProductID,s.DateKey ORDER BY p.ProductID,s.DateKey""",
            (source_system, *product_ids),
        )
        states = _fetch_frame(
            connection,
            """SELECT DISTINCT st.StateID AS state_id FROM dbo.FactSales f
            JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey
            JOIN dbo.DimState st ON st.StateKey=s.StateKey
            WHERE f.SourceSystem=? ORDER BY st.StateID""",
            (source_system,),
        )
    date_keys = sorted(int(value) for value in sales["date_key"].unique())
    return products, list(states["state_id"].astype(str)), sales, date_keys


def _export(data: EnterpriseData, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, frame in data.__dict__.items():
        frame.to_csv(output_directory / f"{name}.csv", index=False)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Phase 3 sample/full generation workflow with meaningful exit codes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use Phase 2 synthetic sample demand")
    parser.add_argument(
        "--no-load", action="store_true", help="Validate and export without SQL writes"
    )
    args = parser.parse_args(argv)
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        config = load_yaml(app.config_dir / "generation.yaml")["generation"]
        source_system = "SYNTHETIC_M5_SAMPLE" if args.sample else "M5"
        inputs = _load_generation_inputs(
            database,
            source_system,
            int(config["sample_product_limit"]),
        )
        generator = EnterpriseGenerator(
            app.random_seed,
            int(config["supplier_count"]),
            int(config["warehouse_count"]),
        )
        data = generator.generate(*inputs)
        repeated = generator.generate(*inputs)
        if data.fingerprints() != repeated.fingerprints():
            raise RuntimeError("Generation is not reproducible for the configured seed")
        validation = validate_enterprise_data(data)
        for check in validation.checks:
            print(f"[PASS] {check}")
        if not validation.passed:
            raise RuntimeError("; ".join(validation.failures))
        _export(data, PROJECT_ROOT / str(config["output_directory"]))
        if not args.no_load:
            with connect(database) as connection:
                try:
                    apply_enterprise_migration(
                        connection,
                        PROJECT_ROOT
                        / "database"
                        / "migrations"
                        / "008_create_enterprise_operational_tables.sql",
                    )
                    load_enterprise_data(
                        connection,
                        data,
                        uuid.uuid4(),
                        int(config["database_batch_size"]),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            with connect(database) as connection:
                counts = {
                    "suppliers": fetch_scalar(
                        connection,
                        "SELECT COUNT(*) FROM dbo.DimSupplier "
                        "WHERE SourceSystem='SYNTHETIC_ENTERPRISE'",
                    ),
                    "warehouses": fetch_scalar(
                        connection,
                        "SELECT COUNT(*) FROM dbo.DimWarehouse "
                        "WHERE SourceSystem='SYNTHETIC_ENTERPRISE'",
                    ),
                    "inventory_snapshots": fetch_scalar(
                        connection,
                        "SELECT COUNT(*) FROM dbo.FactInventorySnapshot "
                        "WHERE SourceSystem='SYNTHETIC_ENTERPRISE'",
                    ),
                    "purchase_orders": fetch_scalar(
                        connection,
                        "SELECT COUNT(*) FROM dbo.FactPurchaseOrder "
                        "WHERE SourceSystem='SYNTHETIC_ENTERPRISE'",
                    ),
                }
                for name, count in counts.items():
                    print(f"database_{name}={count}")
        for name, frame in data.__dict__.items():
            print(f"generated_{name}={len(frame)}")
        print("ENTERPRISE DATA GENERATION PASSED")
        return 0
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        LOGGER.exception("Enterprise data generation failed: %s", exc)
        print("ENTERPRISE DATA GENERATION FAILED")
        return 1
    except Exception as exc:
        LOGGER.exception("Unexpected enterprise data generation failure: %s", exc)
        print("ENTERPRISE DATA GENERATION FAILED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

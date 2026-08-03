"""Memory-bounded, validated M5-to-SQL Server ingestion pipeline."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.ingestion.database_loader import (
    LoadContext,
    upsert_calendar,
    upsert_prices,
    upsert_sales,
    upsert_sales_dimensions,
)
from decision_intelligence.ingestion.schema_validator import (
    DAY_COLUMN_PATTERN,
    M5ValidationError,
    validate_calendar,
    validate_file_set,
    validate_headers,
    validate_prices_chunk,
    validate_sales_chunk,
)
from decision_intelligence.settings import DatabaseSettings

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionConfig:
    """Validated operational settings for an ingestion run."""

    data_directory: Path
    chunk_size: int = 5000
    database_batch_size: int = 2000
    day_block_size: int = 28
    source_system: str = "M5"
    data_version: str = "validation"

    def __post_init__(self) -> None:
        if self.chunk_size <= 0 or self.database_batch_size <= 0 or self.day_block_size <= 0:
            raise ValueError("Ingestion sizes must be positive integers")


@dataclass(frozen=True)
class IngestionResult:
    """Auditable row counts produced by a completed ingestion run."""

    pipeline_run_id: uuid.UUID
    calendar_rows: int
    sales_series_rows: int
    sales_fact_rows: int
    price_source_rows: int
    price_fact_rows: int
    database_sales_rows: int
    database_price_rows: int


class M5IngestionPipeline:
    """Validate and incrementally upsert the three required M5 files."""

    def __init__(self, database: DatabaseSettings, config: IngestionConfig) -> None:
        self.database = database
        self.config = config

    def run(self) -> IngestionResult:
        """Execute calendar, sales, and price loading with chunk-level transactions."""
        paths = validate_file_set(self.config.data_directory)
        headers = validate_headers(paths)
        calendar = validate_calendar(paths["calendar.csv"])
        day_columns = [
            column
            for column in headers["sales_train_validation.csv"]
            if DAY_COLUMN_PATTERN.match(column)
        ]
        calendar_days = set(calendar["d"].astype(str))
        unknown_days = set(day_columns) - calendar_days
        if unknown_days:
            raise M5ValidationError(
                f"Sales day columns are absent from calendar.csv: {sorted(unknown_days)[:5]}"
            )
        day_to_key = {
            str(row.d): int(pd.Timestamp(cast(Any, row.date)).strftime("%Y%m%d"))
            for row in calendar[["d", "date"]].itertuples(index=False)
        }
        pipeline_run_id = uuid.uuid4()
        context = LoadContext(
            pipeline_run_id=pipeline_run_id,
            source_system=self.config.source_system,
            data_version=self.config.data_version,
            batch_size=self.config.database_batch_size,
        )
        with connect(self.database) as connection:
            upsert_calendar(connection, calendar, context)
            connection.commit()
        sales_series_rows = 0
        sales_fact_rows = 0
        known_products: set[str] = set()
        known_stores: set[str] = set()
        seen_sales_ids: set[str] = set()
        sales_reader = pd.read_csv(
            paths["sales_train_validation.csv"], chunksize=self.config.chunk_size
        )
        for chunk_number, chunk in enumerate(sales_reader, start=1):
            validate_sales_chunk(chunk, day_columns)
            chunk_ids = set(chunk["id"].astype(str))
            duplicate_ids = seen_sales_ids & chunk_ids
            if duplicate_ids:
                raise M5ValidationError(
                    f"Sales file contains duplicate id values: {sorted(duplicate_ids)[:5]}"
                )
            seen_sales_ids.update(chunk_ids)
            sales_series_rows += len(chunk)
            known_products.update(chunk["item_id"].astype(str))
            known_stores.update(chunk["store_id"].astype(str))
            with connect(self.database) as connection:
                try:
                    upsert_sales_dimensions(connection, chunk, context)
                    for start in range(0, len(day_columns), self.config.day_block_size):
                        block = day_columns[start : start + self.config.day_block_size]
                        long = chunk[["item_id", "store_id", *block]].melt(
                            id_vars=["item_id", "store_id"],
                            value_vars=block,
                            var_name="d",
                            value_name="quantity",
                        )
                        sales_rows = [
                            (
                                day_to_key[str(row.d)],
                                str(row.item_id),
                                str(row.store_id),
                                float(row.quantity),
                            )
                            for row in long.itertuples(index=False)
                        ]
                        upsert_sales(connection, sales_rows, context)
                        sales_fact_rows += len(sales_rows)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            LOGGER.info("Loaded sales chunk %d (%d series)", chunk_number, len(chunk))
        week_dates = calendar[["wm_yr_wk", "d", "date"]].copy()
        week_dates["date_key"] = week_dates["date"].dt.strftime("%Y%m%d").astype(int)
        price_source_rows = 0
        price_fact_rows = 0
        seen_price_keys: set[tuple[str, str, int]] = set()
        price_reader = pd.read_csv(paths["sell_prices.csv"], chunksize=self.config.chunk_size)
        for chunk_number, chunk in enumerate(price_reader, start=1):
            validate_prices_chunk(chunk)
            chunk_keys = {
                (str(row.store_id), str(row.item_id), int(row.wm_yr_wk))
                for row in chunk[["store_id", "item_id", "wm_yr_wk"]].itertuples(index=False)
            }
            duplicate_price_keys = seen_price_keys & chunk_keys
            if duplicate_price_keys:
                raise M5ValidationError(
                    "Price file contains duplicate business records across chunks: "
                    f"{sorted(duplicate_price_keys)[:5]}"
                )
            seen_price_keys.update(chunk_keys)
            price_source_rows += len(chunk)
            unknown_products = set(chunk["item_id"].astype(str)) - known_products
            unknown_stores = set(chunk["store_id"].astype(str)) - known_stores
            if unknown_products or unknown_stores:
                raise M5ValidationError(
                    "Price identifiers are absent from sales data: "
                    f"products={sorted(unknown_products)[:5]}, stores={sorted(unknown_stores)[:5]}"
                )
            expanded = chunk.merge(week_dates, on="wm_yr_wk", how="left", validate="many_to_many")
            if expanded["date_key"].isna().any():
                missing_weeks = sorted(
                    chunk.loc[~chunk["wm_yr_wk"].isin(week_dates["wm_yr_wk"]), "wm_yr_wk"].unique()
                )
                raise M5ValidationError(
                    f"Prices reference unknown calendar weeks: {missing_weeks[:5]}"
                )
            price_rows = [
                (
                    int(row.date_key),
                    str(row.item_id),
                    str(row.store_id),
                    str(row.wm_yr_wk),
                    float(row.sell_price),
                )
                for row in expanded.itertuples(index=False)
            ]
            with connect(self.database) as connection:
                try:
                    upsert_prices(connection, price_rows, context)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            price_fact_rows += len(price_rows)
            LOGGER.info("Loaded price chunk %d (%d weekly rows)", chunk_number, len(chunk))
        with connect(self.database) as connection:
            database_sales_rows = int(
                fetch_scalar(
                    connection,
                    "SELECT COUNT(*) FROM dbo.FactSales WHERE SourceSystem=? AND DataVersion=?",
                    self.config.source_system,
                    self.config.data_version,
                )
            )
            database_price_rows = int(
                fetch_scalar(
                    connection,
                    "SELECT COUNT(*) FROM dbo.FactSellPrice WHERE SourceSystem=? AND DataVersion=?",
                    self.config.source_system,
                    self.config.data_version,
                )
            )
        return IngestionResult(
            pipeline_run_id=pipeline_run_id,
            calendar_rows=len(calendar),
            sales_series_rows=sales_series_rows,
            sales_fact_rows=sales_fact_rows,
            price_source_rows=price_source_rows,
            price_fact_rows=price_fact_rows,
            database_sales_rows=database_sales_rows,
            database_price_rows=database_price_rows,
        )

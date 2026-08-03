"""SQL-to-Parquet leakage-safe feature pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyodbc

from decision_intelligence.database.connection import connect
from decision_intelligence.features.calendar_features import add_calendar_features
from decision_intelligence.features.inventory_features import add_inventory_features
from decision_intelligence.features.lag_features import add_lag_features
from decision_intelligence.features.price_features import add_price_features
from decision_intelligence.quality.data_quality import assert_latest_quality_gate
from decision_intelligence.settings import DatabaseSettings

LOGGER = logging.getLogger(__name__)


def _query_frame(connection: pyodbc.Connection, source_system: str) -> pd.DataFrame:
    cursor = connection.cursor()
    cursor.execute(
        """WITH inventory AS (
          SELECT DateKey,ProductKey,SUM(OpeningStock) current_stock
          FROM dbo.FactInventorySnapshot GROUP BY DateKey,ProductKey),
        purchase_orders AS (
          SELECT line.ProductKey,
            SUM(CASE WHEN po.Status IN ('OPEN','DELAYED','PARTIAL')
              THEN line.OrderedQuantity-line.ReceivedQuantity-line.CancelledQuantity ELSE 0 END)
              open_purchase_order_quantity,
            SUM(CASE WHEN po.Status IN ('OPEN','DELAYED','PARTIAL')
              THEN line.OrderedQuantity-line.ReceivedQuantity-line.CancelledQuantity ELSE 0 END)
              expected_inbound_quantity
          FROM dbo.FactPurchaseOrder po JOIN dbo.FactPurchaseOrderLine line
            ON line.PurchaseOrderKey=po.PurchaseOrderKey GROUP BY line.ProductKey),
        lead_time AS (
          SELECT ProductKey,AVG(CAST(LeadTimeDays AS float)) supplier_lead_time
          FROM dbo.BridgeSupplierProduct GROUP BY ProductKey)
        SELECT d.FullDate date,d.DateKey date_key,p.ProductID product_id,
          c.CategoryID category_id,s.StoreID store_id,st.StateID state_id,
          CAST(f.Quantity AS float) target,CAST(price.SellPrice AS float) current_price,
          d.EventName event_name,d.EventType event_type,d.SnapCA snap_ca,
          d.SnapTX snap_tx,d.SnapWI snap_wi,
          CAST(i.current_stock AS float) current_stock,
          CAST(po.open_purchase_order_quantity AS float) open_purchase_order_quantity,
          CAST(po.expected_inbound_quantity AS float) expected_inbound_quantity,
          CAST(lt.supplier_lead_time AS float) supplier_lead_time
        FROM dbo.FactSales f JOIN dbo.DimDate d ON d.DateKey=f.DateKey
        JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
        JOIN dbo.DimCategory c ON c.CategoryKey=p.CategoryKey
        JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey JOIN dbo.DimState st ON st.StateKey=s.StateKey
        LEFT JOIN dbo.FactSellPrice price ON price.DateKey=f.DateKey
          AND price.ProductKey=f.ProductKey AND price.StoreKey=f.StoreKey
        LEFT JOIN inventory i ON i.DateKey=f.DateKey AND i.ProductKey=f.ProductKey
        LEFT JOIN purchase_orders po ON po.ProductKey=f.ProductKey
        LEFT JOIN lead_time lt ON lt.ProductKey=f.ProductKey
        WHERE f.SourceSystem=? ORDER BY p.ProductID,s.StoreID,d.FullDate""",
        source_system,
    )
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)


def build_feature_dataset(
    settings: DatabaseSettings,
    output_path: Path,
    source_system: str = "SYNTHETIC_M5_SAMPLE",
) -> pd.DataFrame:
    """Build and persist the complete feature matrix after passing the quality gate."""
    assert_latest_quality_gate(settings)
    with connect(settings) as connection:
        frame = _query_frame(connection, source_system)
    if frame.empty:
        raise RuntimeError(f"No sales rows found for source {source_system}")
    frame["date"] = pd.to_datetime(frame["date"])
    frame["current_price"] = frame.groupby(["product_id", "store_id"])[
        "current_price"
    ].ffill().bfill()
    frame = add_calendar_features(frame)
    frame = add_lag_features(frame)
    frame = add_price_features(frame)
    frame = add_inventory_features(frame)
    frame["product_code"] = pd.Categorical(frame["product_id"]).codes
    frame["store_code"] = pd.Categorical(frame["store_id"]).codes
    if len(frame) != frame[["product_id", "store_id", "date"]].drop_duplicates().shape[0]:
        raise RuntimeError("Feature grain is not unique")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    LOGGER.info("Wrote %d feature rows to %s", len(frame), output_path)
    return frame

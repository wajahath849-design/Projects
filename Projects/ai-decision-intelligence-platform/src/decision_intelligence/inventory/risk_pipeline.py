"""Calculate warehouse-product inventory intelligence and persist it to SQL Server."""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any, cast

import pandas as pd

from decision_intelligence.database.connection import connect
from decision_intelligence.inventory.calculations import (
    classify_inventory,
    days_of_supply,
    projected_inventory,
    reorder_point,
    safety_stock,
    stockout_probability,
)
from decision_intelligence.settings import DatabaseSettings, load_yaml


def _read_inputs(connection: Any) -> pd.DataFrame:
    cursor = connection.execute(
        """WITH latest_inventory AS (
          SELECT i.*,MAX(i.DateKey) OVER() latest_date_key
          FROM dbo.FactInventorySnapshot i),
        forecast AS (
          SELECT f.ProductKey,SUM(f.ForecastQuantity) demand_30,
            STDEV(CAST(f.ForecastQuantity AS float)) demand_std,
            MIN(f.ForecastKey) forecast_key
          FROM dbo.FactForecast f WHERE f.HorizonDays IN (7,30)
          GROUP BY f.ProductKey),
        product_warehouse AS (
          SELECT ProductKey,COUNT(*) warehouse_count FROM latest_inventory
          WHERE DateKey=latest_date_key GROUP BY ProductKey),
        inbound AS (
          SELECT line.ProductKey,po.WarehouseKey,
            SUM(line.OrderedQuantity-line.ReceivedQuantity-line.CancelledQuantity)
              inbound_quantity
          FROM dbo.FactPurchaseOrder po JOIN dbo.FactPurchaseOrderLine line
            ON line.PurchaseOrderKey=po.PurchaseOrderKey
          WHERE po.Status IN ('OPEN','PARTIAL','DELAYED')
          GROUP BY line.ProductKey,po.WarehouseKey),
        lead AS (
          SELECT ProductKey,AVG(CAST(LeadTimeDays AS float)) lead_time
          FROM dbo.BridgeSupplierProduct WHERE ActiveFlag=1 GROUP BY ProductKey)
        SELECT i.DateKey,i.ProductKey,i.WarehouseKey,p.ProductID,w.WarehouseID,
          CAST(i.ClosingStock AS float) current_inventory,
          CAST(COALESCE(b.inbound_quantity,0) AS float) inbound_quantity,
          CAST(COALESCE(f.demand_30,0)/NULLIF(pw.warehouse_count,0)/30.0 AS float)
            mean_daily_demand,
          CAST(COALESCE(f.demand_std,0)/NULLIF(pw.warehouse_count,0) AS float)
            daily_demand_std,
          CAST(COALESCE(l.lead_time,7) AS float) lead_time,
          CAST(w.ServiceLevelTarget AS float) service_level,f.forecast_key
        FROM latest_inventory i JOIN dbo.DimProduct p ON p.ProductKey=i.ProductKey
        JOIN dbo.DimWarehouse w ON w.WarehouseKey=i.WarehouseKey
        JOIN product_warehouse pw ON pw.ProductKey=i.ProductKey
        LEFT JOIN forecast f ON f.ProductKey=i.ProductKey
        LEFT JOIN inbound b ON b.ProductKey=i.ProductKey AND b.WarehouseKey=i.WarehouseKey
        LEFT JOIN lead l ON l.ProductKey=i.ProductKey
        WHERE i.DateKey=i.latest_date_key"""
    )
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)


def _projected_date(date_key: Any, depletion_days: int | None) -> int | None:
    if depletion_days is None or depletion_days > 90:
        return None
    start = pd.to_datetime(str(int(date_key)), format="%Y%m%d")
    return int((start + pd.Timedelta(days=depletion_days)).strftime("%Y%m%d"))


def calculate_inventory_risks(
    settings: DatabaseSettings,
    config_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """Calculate, validate, export, and upsert inventory risks."""
    configuration = load_yaml(config_path)["inventory"]
    horizon = int(configuration["forecast_horizon_days"])
    thresholds = {
        key: float(configuration[key])
        for key in (
            "critical_probability", "at_risk_probability",
            "excess_days_supply", "obsolete_daily_demand",
        )
    }
    with connect(settings) as connection:
        frame = _read_inputs(connection)
    rows: list[dict[str, Any]] = []
    records = cast(list[dict[str, Any]], frame.to_dict(orient="records"))
    for item in records:
        mean = max(float(item["mean_daily_demand"]), 0.0)
        variability = max(float(item["daily_demand_std"]), 0.0)
        lead = max(float(item["lead_time"]), 0.0)
        inventory = max(float(item["current_inventory"]), 0.0)
        inbound = max(float(item["inbound_quantity"]), 0.0)
        buffer = safety_stock(variability, lead, float(item["service_level"]))
        reorder = reorder_point(mean, lead, buffer)
        supply = days_of_supply(
            inventory + inbound, mean, float(configuration["zero_demand_days_supply"])
        )
        projected = projected_inventory(inventory, inbound, mean * horizon)
        probability = stockout_probability(inventory + inbound, mean, variability, horizon)
        classification = classify_inventory(
            inventory, mean, reorder, supply, probability, thresholds
        )
        depletion_days = math.ceil((inventory + inbound) / mean) if mean > 0 else None
        rows.append({
            **item, "safety_stock": buffer, "reorder_point": reorder,
            "days_of_supply": supply, "projected_inventory": projected,
            "stockout_probability": probability,
            "risk_classification": classification,
            "projected_stockout_date_key": _projected_date(
                item["DateKey"], depletion_days
            ),
        })
    result = pd.DataFrame(rows)
    if result.empty:
        raise RuntimeError("No current inventory rows were available")
    _persist_risks(settings, result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    result.to_parquet(output_path.with_suffix(".parquet"), index=False)
    return result


def _persist_risks(settings: DatabaseSettings, result: pd.DataFrame) -> None:
    pipeline_id = uuid.uuid4()
    with connect(settings) as connection:
        connection.execute(
            """IF COL_LENGTH('dbo.FactStockoutRisk','ProjectedInventory') IS NULL
            ALTER TABLE dbo.FactStockoutRisk ADD ProjectedInventory decimal(19,4) NULL"""
        )
        records = []
        for row in result.to_dict(orient="records"):
            projected_date = row["projected_stockout_date_key"]
            if projected_date is not None:
                exists = connection.execute(
                    "SELECT COUNT(*) FROM dbo.DimDate WHERE DateKey=?", int(projected_date)
                ).fetchone()
                if exists is None or int(exists[0]) == 0:
                    projected_date = None
            records.append((
                int(row["DateKey"]), int(row["ProductKey"]), int(row["WarehouseKey"]),
                int(row["forecast_key"]) if row["forecast_key"] is not None else None,
                float(row["current_inventory"]), float(row["safety_stock"]),
                float(row["reorder_point"]), float(row["projected_inventory"]),
                float(row["days_of_supply"]), float(row["stockout_probability"]),
                row["risk_classification"], projected_date, pipeline_id,
                "INVENTORY_INTELLIGENCE", "phase-11-v1",
            ))
        connection.cursor().executemany(
            """MERGE dbo.FactStockoutRisk AS target
            USING (SELECT ? DateKey,? ProductKey,? WarehouseKey) AS source
            ON target.DateKey=source.DateKey AND target.ProductKey=source.ProductKey
              AND target.WarehouseKey=source.WarehouseKey
            WHEN MATCHED THEN UPDATE SET ForecastKey=?,CurrentInventory=?,SafetyStock=?,
              ReorderPoint=?,ProjectedInventory=?,DaysOfSupply=?,StockoutProbability=?,
              RiskClassification=?,ProjectedStockoutDateKey=?,UpdatedAt=SYSUTCDATETIME(),
              PipelineRunID=?,SourceSystem=?,DataVersion=?
            WHEN NOT MATCHED THEN INSERT
              (DateKey,ProductKey,WarehouseKey,ForecastKey,CurrentInventory,SafetyStock,
               ReorderPoint,ProjectedInventory,DaysOfSupply,StockoutProbability,
               RiskClassification,ProjectedStockoutDateKey,PipelineRunID,SourceSystem,DataVersion)
              VALUES (source.DateKey,source.ProductKey,source.WarehouseKey,
                ?,?,?,?,?,?,?,?,?,?,?,?);""",
            [(row[0], row[1], row[2], *row[3:], *row[3:]) for row in records],
        )
        connection.execute(
            """UPDATE f SET StockoutProbability=r.probability
            FROM dbo.FactForecast f JOIN (
              SELECT ProductKey,AVG(StockoutProbability) probability
              FROM dbo.FactStockoutRisk WHERE DataVersion='phase-11-v1' GROUP BY ProductKey
            ) r ON r.ProductKey=f.ProductKey WHERE f.DataVersion='phase-10-v1'"""
        )
        connection.commit()

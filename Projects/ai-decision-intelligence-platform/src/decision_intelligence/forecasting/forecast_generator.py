"""Recursive multi-horizon forecast generation and SQL persistence."""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.settings import DatabaseSettings

FORECAST_NAMESPACE = uuid.UUID("82c3ed88-8e34-4a5a-b830-475b859f4b70")


def _date_key(value: pd.Timestamp) -> int:
    return int(value.strftime("%Y%m%d"))


def _future_row(
    last: pd.Series,
    target_date: pd.Timestamp,
    history: list[float],
) -> dict[str, Any]:
    """Construct one point-in-time feature row from known state and prior predictions."""
    demand_7 = np.asarray(history[-7:], dtype=float)
    demand_14 = np.asarray(history[-14:], dtype=float)
    current_stock = max(float(last.get("current_stock", 0.0)), 0.0)
    rolling_7 = float(demand_7.mean())
    lead_time = float(last.get("supplier_lead_time", 7.0))
    safety_stock = 1.645 * float(demand_7.std(ddof=0)) * math.sqrt(max(lead_time, 0.0))
    reorder_point = rolling_7 * lead_time + safety_stock
    price = float(last.get("current_price", 0.0))
    return {
        "product_id": last["product_id"],
        "category_id": last["category_id"],
        "store_id": last["store_id"],
        "state_id": last["state_id"],
        "product_code": int(last["product_code"]),
        "store_code": int(last["store_code"]),
        "date": target_date,
        "day_of_week": target_date.dayofweek,
        "day_of_month": target_date.day,
        "week_of_year": int(target_date.isocalendar().week),
        "month": target_date.month,
        "quarter": target_date.quarter,
        "year": target_date.year,
        "weekend_flag": int(target_date.dayofweek >= 5),
        "event_flag": 0,
        "event_type_code": -1,
        "snap_flag": 0,
        "lag_1": history[-1],
        "lag_7": history[-7],
        "lag_14": history[-14],
        "rolling_mean_7": rolling_7,
        "rolling_mean_14": float(demand_14.mean()),
        "rolling_std_7": float(demand_7.std(ddof=0)),
        "current_price": price,
        "price_lag_7": price,
        "price_change_percentage": 0.0,
        "relative_price_to_category": 1.0,
        "promotion_proxy": 0,
        "current_stock": current_stock,
        "days_of_supply": current_stock / rolling_7 if rolling_7 > 0 else 999.0,
        "open_purchase_order_quantity": float(last.get("open_purchase_order_quantity", 0.0)),
        "expected_inbound_quantity": float(last.get("expected_inbound_quantity", 0.0)),
        "supplier_lead_time": lead_time,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "stockout_flag": int(current_stock <= reorder_point),
    }


def _ensure_future_dates(connection: Any, dates: list[pd.Timestamp]) -> None:
    rows = []
    for value in dates:
        timestamp = pd.Timestamp(value)
        rows.append((
            _date_key(timestamp), timestamp.date(), timestamp.dayofweek + 1,
            timestamp.day_name(), int(timestamp.isocalendar().week), timestamp.month,
            timestamp.month_name(), timestamp.quarter, timestamp.year,
            int(timestamp.dayofweek >= 5), "FORECAST_PIPELINE", "phase-10-v1",
        ))
    connection.cursor().executemany(
        """IF NOT EXISTS (SELECT 1 FROM dbo.DimDate WHERE DateKey=?)
        INSERT dbo.DimDate
        (DateKey,FullDate,DayOfWeek,DayName,WeekOfYear,MonthNumber,MonthName,
         QuarterNumber,CalendarYear,IsWeekend,SourceSystem,DataVersion)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(row[0], *row) for row in rows],
    )


def _persist_forecasts(
    settings: DatabaseSettings,
    frame: pd.DataFrame,
    selected: dict[str, Any],
    forecast_date: pd.Timestamp,
) -> pd.DataFrame:
    pipeline_id = uuid.uuid4()
    with connect(settings) as connection:
        connection.execute(
            """IF COL_LENGTH('dbo.FactForecast','ForecastConfidence') IS NULL
            ALTER TABLE dbo.FactForecast ADD ForecastConfidence decimal(9,6) NULL"""
        )
        connection.execute(
            """EXEC(N'CREATE OR ALTER VIEW dbo.vw_DemandForecast AS
            SELECT f.ForecastKey, fd.FullDate AS ForecastDate, td.FullDate AS TargetDate,
              p.ProductID, s.StoreID, m.ModelName, f.HorizonDays, f.ForecastQuantity,
              f.LowerBound, f.UpperBound, f.ExpectedRevenue, f.ForecastBias,
              f.ForecastConfidence, f.StockoutProbability
            FROM dbo.FactForecast f
            JOIN dbo.DimDate fd ON fd.DateKey=f.ForecastDateKey
            JOIN dbo.DimDate td ON td.DateKey=f.TargetDateKey
            JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
            LEFT JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey
            JOIN dbo.DimModel m ON m.ModelKey=f.ModelKey')"""
        )
        _ensure_future_dates(connection, sorted(frame["date"].unique()))
        model_key = int(fetch_scalar(
            connection, "SELECT ModelKey FROM dbo.DimModel WHERE ModelID=?", selected["model_id"]
        ))
        product_keys = dict(
            connection.execute("SELECT ProductID,ProductKey FROM dbo.DimProduct").fetchall()
        )
        store_keys = dict(
            connection.execute("SELECT StoreID,StoreKey FROM dbo.DimStore").fetchall()
        )
        merge_rows = []
        for row in frame.to_dict(orient="records"):
            forecast_id = uuid.uuid5(
                FORECAST_NAMESPACE,
                f"{selected['model_id']}|{row['product_id']}|{row['store_id']}|"
                f"{pd.Timestamp(row['date']):%Y-%m-%d}",
            )
            merge_rows.append((
                forecast_id, _date_key(forecast_date), _date_key(pd.Timestamp(row["date"])),
                product_keys[row["product_id"]], store_keys[row["store_id"]], model_key,
                int(selected["model_run_key"]), int(row["horizon_days"]),
                float(row["prediction"]), float(row["lower_bound"]),
                float(row["upper_bound"]), float(row["expected_revenue"]),
                float(selected["bias"]), float(row["confidence"]), pipeline_id,
                "FORECAST_PIPELINE", "phase-10-v1",
            ))
        connection.cursor().executemany(
            """MERGE dbo.FactForecast AS target USING
              (SELECT ? ForecastID,? TargetDateKey,? ProductKey,? StoreKey) AS source
            ON target.TargetDateKey=source.TargetDateKey
              AND target.ProductKey=source.ProductKey AND target.StoreKey=source.StoreKey
              AND target.DataVersion='phase-10-v1'
            WHEN MATCHED THEN UPDATE SET ForecastID=source.ForecastID,ForecastDateKey=?,
              ModelKey=?,ModelRunKey=?,HorizonDays=?,ForecastQuantity=?,
              LowerBound=?,UpperBound=?,ExpectedRevenue=?,ForecastBias=?,ForecastConfidence=?,
              UpdatedAt=SYSUTCDATETIME(),PipelineRunID=?,SourceSystem=?,DataVersion=?
            WHEN NOT MATCHED THEN INSERT
              (ForecastID,ForecastDateKey,TargetDateKey,ProductKey,StoreKey,ModelKey,ModelRunKey,
               HorizonDays,ForecastQuantity,LowerBound,UpperBound,ExpectedRevenue,ForecastBias,
               ForecastConfidence,PipelineRunID,SourceSystem,DataVersion)
              VALUES (source.ForecastID,?,source.TargetDateKey,source.ProductKey,source.StoreKey,
                ?,?,?,?,?,?,?,?,?,?,?,?);""",
            [(
                row[0], row[2], row[3], row[4], row[1], *row[5:],
                row[1], *row[5:],
            ) for row in merge_rows],
        )
        connection.commit()
    result = frame.copy()
    result["forecast_id"] = [str(row[0]) for row in merge_rows]
    return result


def generate_forecasts(
    settings: DatabaseSettings,
    feature_path: Path,
    metadata_path: Path,
    output_directory: Path,
    horizon_days: int = 90,
) -> pd.DataFrame:
    """Generate recursive daily forecasts and persist detail plus aggregate exports."""
    features = pd.read_parquet(feature_path).sort_values(["product_id", "store_id", "date"])
    selected = json.loads(metadata_path.read_text(encoding="utf-8"))
    artifact_path = Path(selected["artifact_path"])
    if not artifact_path.is_absolute():
        artifact_path = metadata_path.resolve().parents[2] / artifact_path
    payload = joblib.load(artifact_path)
    model, model_features = payload["model"], payload["features"]
    forecast_date = pd.Timestamp(features["date"].max())
    rows: list[dict[str, Any]] = []
    for (_, _), group in features.groupby(["product_id", "store_id"], sort=True):
        last = group.iloc[-1]
        history = group["target"].astype(float).tolist()
        for step in range(1, horizon_days + 1):
            target_date = forecast_date + pd.Timedelta(days=step)
            row = _future_row(last, target_date, history)
            prediction = max(float(model.predict(pd.DataFrame([row]), model_features)[0]), 0.0)
            history.append(prediction)
            interval = 1.96 * float(selected["residual_std"]) * math.sqrt(max(step, 1) / 7)
            lower, upper = max(0.0, prediction - interval), prediction + interval
            row.update({
                "prediction": prediction,
                "lower_bound": lower,
                "upper_bound": upper,
                "confidence": float(np.clip(
                    1.0 / (1.0 + (upper - lower) / (prediction + 1.0)), 0, 1
                )),
                "horizon_days": 7 if step <= 7 else 30 if step <= 30 else 90,
                "expected_revenue": prediction * float(row["current_price"]),
                "model_id": selected["model_id"],
                "model_version": "phase-10-v1",
            })
            rows.append(row)
    result = _persist_forecasts(
        settings, pd.DataFrame(rows), selected, forecast_date
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_directory / "forecast_detail.parquet", index=False)
    result.to_csv(output_directory / "forecast_detail.csv", index=False)
    for level, columns in {
        "category": ["category_id", "date", "horizon_days"],
        "store": ["store_id", "date", "horizon_days"],
        "state": ["state_id", "date", "horizon_days"],
        "company": ["date", "horizon_days"],
    }.items():
        result.groupby(columns, as_index=False)[
            ["prediction", "lower_bound", "upper_bound", "expected_revenue"]
        ].sum().to_csv(output_directory / f"forecast_{level}.csv", index=False)
    return result

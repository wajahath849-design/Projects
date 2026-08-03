"""SQL-backed scenario seeding, execution, comparison, and persistence."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, cast

import pandas as pd

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.scenarios.engine import apply_scenario
from decision_intelligence.settings import DatabaseSettings, load_yaml


def _query_frame(connection: Any, sql: str, *parameters: Any) -> pd.DataFrame:
    cursor = connection.execute(sql, parameters)
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)


def _load_baseline(settings: DatabaseSettings) -> pd.DataFrame:
    with connect(settings) as connection:
        return _query_frame(connection, """WITH demand AS (
          SELECT ProductKey,SUM(ForecastQuantity) baseline_demand
          FROM dbo.FactForecast WHERE HorizonDays IN (7,30) GROUP BY ProductKey),
        warehouse_count AS (
          SELECT ProductKey,COUNT(*) warehouse_count FROM dbo.FactStockoutRisk
          WHERE DataVersion='phase-11-v1' GROUP BY ProductKey),
        recommendation AS (
          SELECT ProductKey,WarehouseKey,SUM(RecommendedOrderQuantity) baseline_order_quantity,
            SUM(ExpectedPurchaseCost) baseline_purchase_cost,
            SUM(ExpectedTransportationCost) baseline_transportation_cost,
            SUM(ExpectedHoldingCost) baseline_holding_cost,
            SUM(ExpectedTotalCost) baseline_total_cost,
            SUM(ExpectedRevenueProtected) baseline_revenue_protected
          FROM dbo.FactOptimizationRecommendation WHERE DataVersion='phase-12-v1'
          GROUP BY ProductKey,WarehouseKey)
        SELECT r.DateKey date_key,r.ProductKey product_key,r.WarehouseKey warehouse_key,
          p.ProductID product_id,w.WarehouseID warehouse_id,
          CAST(COALESCE(d.baseline_demand,0)/NULLIF(wc.warehouse_count,0) AS float)
            baseline_demand,
          CAST(COALESCE(price.average_price,0) AS float) average_price,
          CAST(r.CurrentInventory AS float) baseline_inventory,
          CAST(r.StockoutProbability AS float) baseline_stockout_probability,
          CAST(COALESCE(rec.baseline_order_quantity,0) AS float) baseline_order_quantity,
          CAST(COALESCE(rec.baseline_purchase_cost,0) AS float) baseline_purchase_cost,
          CAST(COALESCE(rec.baseline_transportation_cost,0) AS float)
            baseline_transportation_cost,
          CAST(COALESCE(rec.baseline_holding_cost,0) AS float) baseline_holding_cost,
          CAST(COALESCE(rec.baseline_total_cost,0) AS float) baseline_total_cost,
          CAST(COALESCE(rec.baseline_revenue_protected,0) AS float)
            baseline_revenue_protected,
          CAST(COALESCE(cost.average_purchase_cost,0) AS float) average_purchase_cost
        FROM dbo.FactStockoutRisk r JOIN dbo.DimProduct p ON p.ProductKey=r.ProductKey
        JOIN dbo.DimWarehouse w ON w.WarehouseKey=r.WarehouseKey
        JOIN warehouse_count wc ON wc.ProductKey=r.ProductKey
        LEFT JOIN demand d ON d.ProductKey=r.ProductKey
        LEFT JOIN recommendation rec ON rec.ProductKey=r.ProductKey
          AND rec.WarehouseKey=r.WarehouseKey
        OUTER APPLY (SELECT AVG(CAST(SellPrice AS float)) average_price
          FROM dbo.FactSellPrice sp WHERE sp.ProductKey=r.ProductKey) price
        OUTER APPLY (SELECT AVG(CAST(PurchaseCost AS float)) average_purchase_cost
          FROM dbo.BridgeSupplierProduct bp WHERE bp.ProductKey=r.ProductKey) cost
        WHERE r.DataVersion='phase-11-v1'""")


def seed_scenarios(settings: DatabaseSettings, config_path: Path) -> list[str]:
    """Idempotently seed every configured scenario definition."""
    definitions = load_yaml(config_path)["scenarios"]
    with connect(settings) as connection:
        for scenario_id, definition in definitions.items():
            connection.execute(
                """MERGE dbo.DimScenario AS target USING (SELECT ? ScenarioID) source
                ON target.ScenarioID=source.ScenarioID
                WHEN MATCHED THEN UPDATE SET ScenarioName=?,ScenarioType=?,ParameterName=?,
                  BaselineValue=?,ScenarioValue=?,IsBaseline=0,UpdatedAt=SYSUTCDATETIME(),
                  SourceSystem='SCENARIO_ENGINE',DataVersion='phase-13-v1'
                WHEN NOT MATCHED THEN INSERT
                  (ScenarioID,ScenarioName,ScenarioType,ParameterName,BaselineValue,
                   ScenarioValue,IsBaseline,SourceSystem,DataVersion)
                  VALUES (source.ScenarioID,?,?,?,?,?,0,'SCENARIO_ENGINE','phase-13-v1');""",
                scenario_id, definition["name"], definition["type"],
                definition["parameter"], float(definition["baseline"]),
                float(definition["value"]), definition["name"], definition["type"],
                definition["parameter"], float(definition["baseline"]),
                float(definition["value"]),
            )
        connection.commit()
    return list(definitions)


def _ensure_columns(connection: Any) -> None:
    columns = {
        "BaselinePurchaseCost": "decimal(19,4)",
        "ScenarioPurchaseCost": "decimal(19,4)",
        "BaselineTransportationCost": "decimal(19,4)",
        "ScenarioTransportationCost": "decimal(19,4)",
        "BaselineHoldingCost": "decimal(19,4)",
        "ScenarioHoldingCost": "decimal(19,4)",
        "BaselineRevenueProtected": "decimal(19,4)",
        "ScenarioRevenueProtected": "decimal(19,4)",
    }
    for name, data_type in columns.items():
        connection.execute(
            f"""IF COL_LENGTH('dbo.FactScenarioResult','{name}') IS NULL
            ALTER TABLE dbo.FactScenarioResult ADD {name} {data_type} NULL"""
        )


def _persist_results(
    settings: DatabaseSettings,
    scenario_key: int,
    result: pd.DataFrame,
) -> None:
    pipeline_id = uuid.uuid4()
    columns = [
        "ScenarioKey", "DateKey", "ProductKey", "WarehouseKey",
        "BaselineDemand", "ScenarioDemand", "BaselineRevenue", "ScenarioRevenue",
        "BaselineInventory", "ScenarioInventory", "BaselineStockoutProbability",
        "ScenarioStockoutProbability", "BaselineOrderQuantity", "ScenarioOrderQuantity",
        "BaselinePurchaseCost", "ScenarioPurchaseCost", "BaselineTransportationCost",
        "ScenarioTransportationCost", "BaselineHoldingCost", "ScenarioHoldingCost",
        "BaselineTotalCost", "ScenarioTotalCost", "BaselineProfit", "ScenarioProfit",
        "BaselineRevenueProtected", "ScenarioRevenueProtected", "RevenueProtected",
        "PipelineRunID", "SourceSystem", "DataVersion",
    ]
    update_columns = columns[4:]
    update_sql = ",".join(f"{column}=?" for column in update_columns)
    insert_columns = ",".join(columns)
    insert_values = ",".join("?" for _ in columns)
    with connect(settings) as connection:
        _ensure_columns(connection)
        for row in result.to_dict(orient="records"):
            values = (
                scenario_key, int(row["date_key"]), int(row["product_key"]),
                int(row["warehouse_key"]), float(row["baseline_demand"]),
                float(row["scenario_demand"]), float(row["baseline_revenue"]),
                float(row["scenario_revenue"]), float(row["baseline_inventory"]),
                float(row["scenario_inventory"]),
                float(row["baseline_stockout_probability"]),
                float(row["scenario_stockout_probability"]),
                float(row["baseline_order_quantity"]),
                float(row["scenario_order_quantity"]),
                float(row["baseline_purchase_cost"]), float(row["scenario_purchase_cost"]),
                float(row["baseline_transportation_cost"]),
                float(row["scenario_transportation_cost"]),
                float(row["baseline_holding_cost"]), float(row["scenario_holding_cost"]),
                float(row["baseline_total_cost"]), float(row["scenario_total_cost"]),
                float(row["baseline_profit"]), float(row["scenario_profit"]),
                float(row["baseline_revenue_protected"]),
                float(row["scenario_revenue_protected"]),
                float(row["scenario_revenue_protected"]), pipeline_id,
                "SCENARIO_ENGINE", "phase-13-v1",
            )
            exists = int(fetch_scalar(
                connection,
                """SELECT COUNT(*) FROM dbo.FactScenarioResult
                WHERE ScenarioKey=? AND DateKey=? AND ProductKey=? AND WarehouseKey=?""",
                *values[:4],
            ))
            if exists:
                connection.execute(
                    f"""UPDATE dbo.FactScenarioResult SET {update_sql},
                    UpdatedAt=SYSUTCDATETIME() WHERE ScenarioKey=? AND DateKey=?
                    AND ProductKey=? AND WarehouseKey=?""",
                    *values[4:], *values[:4],
                )
            else:
                connection.execute(
                    f"INSERT dbo.FactScenarioResult ({insert_columns}) VALUES ({insert_values})",
                    *values,
                )
        connection.commit()


def run_scenario(settings: DatabaseSettings, scenario_id: str) -> pd.DataFrame:
    """Run one persisted scenario against an unchanged baseline."""
    with connect(settings) as connection:
        definition = connection.execute(
            """SELECT ScenarioKey,ScenarioType,BaselineValue,ScenarioValue
            FROM dbo.DimScenario WHERE ScenarioID=?""",
            scenario_id,
        ).fetchone()
    if definition is None:
        raise KeyError(f"Scenario not found: {scenario_id}")
    baseline = _load_baseline(settings)
    output_rows: list[dict[str, Any]] = []
    baseline_rows = cast(list[dict[str, Any]], baseline.to_dict(orient="records"))
    for row in baseline_rows:
        row["baseline_revenue"] = float(row["baseline_demand"]) * float(row["average_price"])
        row["baseline_profit"] = float(row["baseline_revenue"]) - float(
            row["baseline_total_cost"]
        )
        adjusted = apply_scenario(
            row, str(definition[1]), float(definition[2]), float(definition[3])
        )
        output_rows.append({**row, **adjusted, "scenario_id": scenario_id})
    result = pd.DataFrame(output_rows)
    _persist_results(settings, int(definition[0]), result)
    return result


def run_all_scenarios(
    settings: DatabaseSettings,
    config_path: Path,
    output_directory: Path,
) -> pd.DataFrame:
    """Seed and run every required scenario and export baseline comparisons."""
    scenario_ids = seed_scenarios(settings, config_path)
    results = pd.concat(
        [run_scenario(settings, scenario_id) for scenario_id in scenario_ids],
        ignore_index=True,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_directory / "scenario_results.csv", index=False)
    results.to_parquet(output_directory / "scenario_results.parquet", index=False)
    summary = results.groupby("scenario_id", as_index=False).agg(
        demand_impact=("scenario_demand", "sum"),
        revenue_impact=("scenario_revenue", "sum"),
        cost_impact=("scenario_total_cost", "sum"),
        profit_impact=("scenario_profit", "sum"),
        stockout_probability=("scenario_stockout_probability", "mean"),
        order_quantity=("scenario_order_quantity", "sum"),
    )
    for scenario_id in scenario_ids:
        selected = results[results["scenario_id"] == scenario_id]
        summary.loc[summary["scenario_id"] == scenario_id, "demand_impact"] -= selected[
            "baseline_demand"
        ].sum()
        summary.loc[summary["scenario_id"] == scenario_id, "revenue_impact"] -= selected[
            "baseline_revenue"
        ].sum()
        summary.loc[summary["scenario_id"] == scenario_id, "cost_impact"] -= selected[
            "baseline_total_cost"
        ].sum()
        summary.loc[summary["scenario_id"] == scenario_id, "profit_impact"] -= selected[
            "baseline_profit"
        ].sum()
    summary.to_csv(output_directory / "scenario_summary.csv", index=False)
    (output_directory / "scenario_summary.json").write_text(
        json.dumps(summary.to_dict(orient="records"), indent=2), encoding="utf-8"
    )
    return results

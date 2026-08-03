"""SQL-backed replenishment optimization pipeline."""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any, cast

import pandas as pd

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.optimization.optimizer import (
    OptimizationSolution,
    solve_replenishment,
)
from decision_intelligence.settings import DatabaseSettings, load_yaml

RECOMMENDATION_NAMESPACE = uuid.UUID("a56ece5a-e59e-48dc-851f-60fdcde8fcec")


def _query_frame(connection: Any, sql: str) -> pd.DataFrame:
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)


def _load_problem(
    settings: DatabaseSettings,
    planning_horizon_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    with connect(settings) as connection:
        requirements = _query_frame(connection, """WITH demand AS (
          SELECT ProductKey,SUM(ForecastQuantity) demand_30
          FROM dbo.FactForecast WHERE HorizonDays IN (7,30) GROUP BY ProductKey),
        warehouse_count AS (
          SELECT ProductKey,COUNT(*) warehouse_count FROM dbo.FactStockoutRisk
          WHERE DataVersion='phase-11-v1' GROUP BY ProductKey),
        inbound AS (
          SELECT line.ProductKey,po.WarehouseKey,
            SUM(line.OrderedQuantity-line.ReceivedQuantity-line.CancelledQuantity) inbound
          FROM dbo.FactPurchaseOrder po JOIN dbo.FactPurchaseOrderLine line
            ON line.PurchaseOrderKey=po.PurchaseOrderKey
          WHERE po.Status IN ('OPEN','PARTIAL','DELAYED')
          GROUP BY line.ProductKey,po.WarehouseKey)
        SELECT r.DateKey date_key,r.ProductKey product_key,r.WarehouseKey warehouse_key,
          p.ProductID product_id,w.WarehouseID warehouse_id,r.ForecastKey forecast_key,
          CAST(r.CurrentInventory AS float) current_inventory,
          CAST(COALESCE(i.inbound,0) AS float) inbound_quantity,
          CAST(r.SafetyStock AS float) safety_stock,
          CAST(COALESCE(d.demand_30,0)/NULLIF(wc.warehouse_count,0) AS float)
            horizon_demand,
          CAST(CASE WHEN COALESCE(d.demand_30,0)/NULLIF(wc.warehouse_count,0)
              +r.SafetyStock-r.CurrentInventory-COALESCE(i.inbound,0)>0
            THEN COALESCE(d.demand_30,0)/NULLIF(wc.warehouse_count,0)
              +r.SafetyStock-r.CurrentInventory-COALESCE(i.inbound,0) ELSE 0 END AS float)
            required_quantity,
          CAST(r.StockoutProbability AS float) stockout_probability,
          r.RiskClassification risk_classification,
          CAST(COALESCE(price.average_price,0) AS float) average_price
        FROM dbo.FactStockoutRisk r JOIN dbo.DimProduct p ON p.ProductKey=r.ProductKey
        JOIN dbo.DimWarehouse w ON w.WarehouseKey=r.WarehouseKey
        JOIN warehouse_count wc ON wc.ProductKey=r.ProductKey
        LEFT JOIN demand d ON d.ProductKey=r.ProductKey
        LEFT JOIN inbound i ON i.ProductKey=r.ProductKey AND i.WarehouseKey=r.WarehouseKey
        OUTER APPLY (SELECT AVG(CAST(SellPrice AS float)) average_price
          FROM dbo.FactSellPrice sp WHERE sp.ProductKey=r.ProductKey) price
        WHERE r.DataVersion='phase-11-v1'""")
        candidates = _query_frame(connection, f"""WITH current_load AS (
          SELECT WarehouseKey,SUM(ClosingStock) current_units FROM dbo.FactInventorySnapshot
          WHERE DateKey=(SELECT MAX(DateKey) FROM dbo.FactInventorySnapshot)
          GROUP BY WarehouseKey)
        SELECT sp.ProductKey product_key,sp.SupplierKey supplier_key,
          lane.WarehouseKey warehouse_key,p.ProductID product_id,s.SupplierID supplier_id,
          w.WarehouseID warehouse_id,CAST(sp.PurchaseCost AS float) purchase_cost,
          CAST(sp.MinimumOrderQuantity AS float) minimum_order_quantity,
          CAST(sp.MaximumOrderQuantity AS float) maximum_order_quantity,
          CAST(sp.DailyCapacity AS float) daily_capacity,
          CAST(s.DailyCapacity AS float) supplier_daily_capacity,
          CAST(sp.LeadTimeDays AS float) lead_time_days,
          CAST(s.DelayProbability AS float) delay_probability,
          CAST(lane.BaseShippingCost AS float) base_shipping_cost,
          CAST(lane.ShippingCostPerUnit AS float) shipping_cost_per_unit,
          CAST(lane.AverageTransitDays AS float) average_transit_days,
          CAST(w.HoldingCostPerUnitDay AS float) holding_cost_per_unit_day,
          CAST(w.CapacityUnits-COALESCE(load.current_units,0) AS float)
            warehouse_available_capacity
        FROM dbo.BridgeSupplierProduct sp JOIN dbo.DimProduct p ON p.ProductKey=sp.ProductKey
        JOIN dbo.DimSupplier s ON s.SupplierKey=sp.SupplierKey
        JOIN dbo.FactTransportation lane ON lane.SupplierKey=sp.SupplierKey
        JOIN dbo.DimWarehouse w ON w.WarehouseKey=lane.WarehouseKey
        LEFT JOIN current_load load ON load.WarehouseKey=w.WarehouseKey
        WHERE sp.ActiveFlag=1 AND s.ActiveFlag=1 AND w.ActiveFlag=1
          AND sp.LeadTimeDays+lane.AverageTransitDays<={planning_horizon_days}""")
        budget = float(fetch_scalar(
            connection,
            """SELECT TOP 1 ParameterValue FROM dbo.BusinessConstraint
            WHERE ConstraintType='BUDGET' AND ActiveFlag=1 ORDER BY EffectiveDateKey DESC""",
        ))
    candidates = candidates.merge(
        requirements[["product_key", "warehouse_key"]].drop_duplicates(),
        on=["product_key", "warehouse_key"], how="inner",
    )
    return candidates, requirements, budget


def _date_key_after(date_key: int, days: float) -> int:
    start = pd.to_datetime(str(date_key), format="%Y%m%d")
    return int((start + pd.Timedelta(days=math.ceil(days))).strftime("%Y%m%d"))


def _enrich_orders(
    solution: OptimizationSolution,
    requirements: pd.DataFrame,
    penalties: dict[str, float],
) -> pd.DataFrame:
    if solution.orders.empty:
        return solution.orders
    orders = solution.orders.merge(
        requirements, on=["product_key", "warehouse_key", "product_id", "warehouse_id"],
        how="left", suffixes=("", "_requirement"),
    )
    quantity = orders["recommended_order_quantity"]
    order_records = cast(list[dict[str, Any]], orders.to_dict(orient="records"))
    orders["recommendation_id"] = [str(uuid.uuid5(
        RECOMMENDATION_NAMESPACE,
        f"{row['date_key']}|{row['product_key']}|{row['supplier_key']}|"
        f"{row['warehouse_key']}|phase-12-v1",
    )) for row in order_records]
    orders["recommended_order_date_key"] = orders["date_key"]
    orders["expected_delivery_date_key"] = [
        _date_key_after(
            int(row["date_key"]),
            float(row["lead_time_days"]) + float(row["average_transit_days"]),
        )
        for row in order_records
    ]
    orders["expected_purchase_cost"] = quantity * orders["purchase_cost"]
    orders["expected_transportation_cost"] = (
        orders["base_shipping_cost"] + quantity * orders["shipping_cost_per_unit"]
    )
    orders["expected_holding_cost"] = (
        quantity * orders["holding_cost_per_unit_day"] * orders["lead_time_days"]
    )
    uncovered = (orders["required_quantity"] - quantity).clip(lower=0)
    orders["expected_stockout_cost"] = uncovered * penalties["stockout"]
    orders["expected_total_cost"] = orders[
        ["expected_purchase_cost", "expected_transportation_cost",
         "expected_holding_cost", "expected_stockout_cost"]
    ].sum(axis=1)
    protected_units = pd.concat([quantity, orders["required_quantity"]], axis=1).min(axis=1)
    orders["expected_revenue_protected"] = protected_units * orders["average_price"]
    coverage = (quantity / orders["required_quantity"].replace(0, 1)).clip(upper=1)
    orders["expected_stockout_reduction"] = (
        coverage * orders["stockout_probability"]
    ).clip(lower=0, upper=1)
    orders["expected_inventory_after_replenishment"] = (
        orders["current_inventory"] + orders["inbound_quantity"] + quantity
        - orders["horizon_demand"]
    )
    orders["estimated_financial_impact"] = (
        orders["expected_revenue_protected"] - orders["expected_total_cost"]
    )
    priorities = {"Critical": "CRITICAL", "At Risk": "HIGH", "Healthy": "MEDIUM"}
    orders["recommendation_priority"] = orders["risk_classification"].map(
        priorities
    ).fillna("LOW")
    return orders


def _persist_orders(
    settings: DatabaseSettings,
    orders: pd.DataFrame,
    solution: OptimizationSolution,
) -> None:
    if orders.empty:
        return
    pipeline_id = uuid.uuid4()
    with connect(settings) as connection:
        records = []
        for row in orders.to_dict(orient="records"):
            records.append((
                uuid.UUID(str(row["recommendation_id"])), int(row["date_key"]),
                int(row["product_key"]), int(row["supplier_key"]), int(row["warehouse_key"]),
                int(row["forecast_key"]) if row["forecast_key"] is not None else None,
                float(row["recommended_order_quantity"]),
                int(row["recommended_order_date_key"]), int(row["expected_delivery_date_key"]),
                float(row["safety_stock"]),
                float(row["expected_inventory_after_replenishment"]),
                float(row["expected_purchase_cost"]),
                float(row["expected_transportation_cost"]),
                float(row["expected_holding_cost"]), float(row["expected_stockout_cost"]),
                float(row["expected_total_cost"]), float(row["expected_revenue_protected"]),
                float(row["expected_stockout_reduction"]),
                float(row["estimated_financial_impact"]), row["recommendation_priority"],
                solution.status, "All configured constraints independently validated.",
                pipeline_id, "REPLENISHMENT_OPTIMIZER", "phase-12-v1",
            ))
        sql = """MERGE dbo.FactOptimizationRecommendation AS target
        USING (SELECT ? RecommendationID) AS source
        ON target.RecommendationID=source.RecommendationID
        WHEN MATCHED THEN UPDATE SET DateKey=?,ProductKey=?,SupplierKey=?,WarehouseKey=?,
          ForecastKey=?,ScenarioKey=NULL,RecommendedOrderQuantity=?,RecommendedOrderDateKey=?,
          ExpectedDeliveryDateKey=?,SafetyStock=?,ExpectedInventoryAfterReplenishment=?,
          ExpectedPurchaseCost=?,ExpectedTransportationCost=?,ExpectedHoldingCost=?,
          ExpectedStockoutCost=?,ExpectedTotalCost=?,ExpectedRevenueProtected=?,
          ExpectedStockoutReduction=?,EstimatedFinancialImpact=?,RecommendationPriority=?,
          SolverStatus=?,DiagnosticMessage=?,UpdatedAt=SYSUTCDATETIME(),PipelineRunID=?,
          SourceSystem=?,DataVersion=?
        WHEN NOT MATCHED THEN INSERT
          (RecommendationID,DateKey,ProductKey,SupplierKey,WarehouseKey,ForecastKey,ScenarioKey,
           RecommendedOrderQuantity,RecommendedOrderDateKey,ExpectedDeliveryDateKey,SafetyStock,
           ExpectedInventoryAfterReplenishment,ExpectedPurchaseCost,ExpectedTransportationCost,
           ExpectedHoldingCost,ExpectedStockoutCost,ExpectedTotalCost,ExpectedRevenueProtected,
           ExpectedStockoutReduction,EstimatedFinancialImpact,RecommendationPriority,SolverStatus,
           DiagnosticMessage,PipelineRunID,SourceSystem,DataVersion)
          VALUES (source.RecommendationID,?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);"""
        connection.cursor().executemany(
            sql, [(row[0], *row[1:], *row[1:]) for row in records]
        )
        for row in orders.to_dict(orient="records"):
            recommendation_key = int(fetch_scalar(
                connection,
                """SELECT OptimizationRecommendationKey
                FROM dbo.FactOptimizationRecommendation WHERE RecommendationID=?""",
                uuid.UUID(str(row["recommendation_id"])),
            ))
            capacity_before = float(row["warehouse_available_capacity"])
            quantity = float(row["recommended_order_quantity"])
            connection.execute(
                """MERGE dbo.FactOptimizationAllocation AS target
                USING (SELECT ? OptimizationRecommendationKey,? WarehouseKey) source
                ON target.OptimizationRecommendationKey=source.OptimizationRecommendationKey
                  AND target.WarehouseKey=source.WarehouseKey
                WHEN MATCHED THEN UPDATE SET AllocatedQuantity=?,CapacityBefore=?,
                  CapacityAfter=?,AllocationCost=?,UpdatedAt=SYSUTCDATETIME(),PipelineRunID=?,
                  SourceSystem=?,DataVersion=?
                WHEN NOT MATCHED THEN INSERT
                  (OptimizationRecommendationKey,WarehouseKey,AllocatedQuantity,CapacityBefore,
                   CapacityAfter,AllocationCost,PipelineRunID,SourceSystem,DataVersion)
                  VALUES (source.OptimizationRecommendationKey,source.WarehouseKey,
                    ?,?,?,?,?,?,?);""",
                recommendation_key, int(row["warehouse_key"]), quantity, capacity_before,
                capacity_before - quantity, float(row["expected_transportation_cost"]),
                pipeline_id, "REPLENISHMENT_OPTIMIZER", "phase-12-v1",
                quantity, capacity_before, capacity_before - quantity,
                float(row["expected_transportation_cost"]), pipeline_id,
                "REPLENISHMENT_OPTIMIZER", "phase-12-v1",
            )
        connection.commit()


def run_optimization(
    settings: DatabaseSettings,
    config_path: Path,
    output_directory: Path,
) -> OptimizationSolution:
    """Load, solve, validate, enrich, persist, and report replenishment decisions."""
    config = load_yaml(config_path)["optimization"]
    horizon = int(config["planning_horizon_days"])
    candidates, requirements, budget = _load_problem(settings, horizon)
    penalties = {
        "stockout": float(config["stockout_penalty_per_unit"]),
        "late": float(config["late_delivery_risk_weight"]),
        "excess": float(config["excess_inventory_penalty_per_unit"]),
    }
    solution = solve_replenishment(
        candidates, requirements, budget, horizon,
        int(config["solver_time_limit_seconds"]), penalties,
    )
    orders = _enrich_orders(solution, requirements, penalties)
    final = OptimizationSolution(
        solution.status, solution.objective_value, orders, solution.diagnostics
    )
    if final.status not in {"OPTIMAL", "FEASIBLE"} or final.diagnostics:
        raise RuntimeError("; ".join(final.diagnostics) or f"Solver status {final.status}")
    _persist_orders(settings, orders, final)
    output_directory.mkdir(parents=True, exist_ok=True)
    orders.to_csv(output_directory / "recommendations.csv", index=False)
    orders.to_parquet(output_directory / "recommendations.parquet", index=False)
    (output_directory / "diagnostics.json").write_text(json.dumps({
        "solver_status": final.status,
        "objective_value": final.objective_value,
        "constraint_failures": list(final.diagnostics),
        "recommendation_count": len(orders),
        "budget": budget,
        "planning_horizon_days": horizon,
    }, indent=2), encoding="utf-8")
    return final

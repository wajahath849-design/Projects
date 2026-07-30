from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.adjustments import apply_adjustments
from app.db import SessionLocal
from app.forecasting import ForecastResult, forecast_group, prepare_daily_demand
from app.safety_stock import ReplenishmentInputs, calculate_replenishment, round_order_quantity
from app.network_rebalancing import run_network_rebalancing


logger = logging.getLogger(__name__)
settings = get_settings()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _create_model_run(session: Session, horizon_days: int) -> int:
    row = session.execute(
        text(
            """
            INSERT INTO inventory.model_runs
                (model_name, model_version, horizon_days, parameters, status)
            VALUES
                (:model_name, :model_version, :horizon_days, CAST(:parameters AS JSONB), 'RUNNING')
            RETURNING model_run_id
            """
        ),
        {
            "model_name": "hybrid_lightgbm_seasonal_naive",
            "model_version": "1.0.0",
            "horizon_days": horizon_days,
            "parameters": json.dumps(
                {
                    "horizon_days": horizon_days,
                    "min_training_days": settings.min_training_days,
                    "default_service_level": settings.default_service_level,
                }
            ),
        },
    ).scalar_one()
    session.commit()
    return int(row)


def _finish_model_run(session: Session, model_run_id: int, status: str, error_message: str | None = None) -> None:
    session.execute(
        text(
            """
            UPDATE inventory.model_runs
            SET status = :status,
                finished_at = CURRENT_TIMESTAMP,
                error_message = :error_message
            WHERE model_run_id = :model_run_id
            """
        ),
        {"status": status, "error_message": error_message, "model_run_id": model_run_id},
    )
    session.commit()


def _load_transactions(session: Session) -> pd.DataFrame:
    query = text(
        """
        SELECT transaction_ts, warehouse_id, sku_id, transaction_type, quantity
        FROM inventory.inventory_transactions
        WHERE transaction_ts >= CURRENT_DATE - INTERVAL '730 days'
        ORDER BY transaction_ts
        """
    )
    return pd.read_sql(query, session.connection())


def _store_forecast_result(
    session: Session,
    model_run_id: int,
    warehouse_id: int,
    sku_id: int,
    result: ForecastResult,
) -> int:
    records = []
    for row in result.forecast.itertuples(index=False):
        records.append(
            {
                "model_run_id": model_run_id,
                "forecast_date": row.forecast_date,
                "warehouse_id": warehouse_id,
                "sku_id": sku_id,
                "forecast_qty": float(row.forecast_qty),
                "lower_qty": float(row.lower_qty),
                "upper_qty": float(row.upper_qty),
                "model_name": result.model_name,
            }
        )
    if records:
        session.execute(
            text(
                """
                INSERT INTO inventory.demand_forecasts
                    (model_run_id, forecast_date, warehouse_id, sku_id, forecast_qty,
                     lower_qty, upper_qty, model_name)
                VALUES
                    (:model_run_id, :forecast_date, :warehouse_id, :sku_id, :forecast_qty,
                     :lower_qty, :upper_qty, :model_name)
                ON CONFLICT (model_run_id, forecast_date, warehouse_id, sku_id) DO UPDATE SET
                    forecast_qty = EXCLUDED.forecast_qty,
                    lower_qty = EXCLUDED.lower_qty,
                    upper_qty = EXCLUDED.upper_qty,
                    model_name = EXCLUDED.model_name,
                    created_at = CURRENT_TIMESTAMP
                """
            ),
            records,
        )

    metrics = result.metrics
    session.execute(
        text(
            """
            INSERT INTO inventory.forecast_accuracy
                (model_run_id, warehouse_id, sku_id, metric_date, mae, rmse, wape, bias, sample_count,
                 absolute_error_sum, actual_sum, forecast_sum)
            VALUES
                (:model_run_id, :warehouse_id, :sku_id, CURRENT_DATE, :mae, :rmse, :wape, :bias, :sample_count,
                 :absolute_error_sum, :actual_sum, :forecast_sum)
            ON CONFLICT (model_run_id, warehouse_id, sku_id) DO UPDATE SET
                metric_date = EXCLUDED.metric_date,
                mae = EXCLUDED.mae,
                rmse = EXCLUDED.rmse,
                wape = EXCLUDED.wape,
                bias = EXCLUDED.bias,
                sample_count = EXCLUDED.sample_count,
                absolute_error_sum = EXCLUDED.absolute_error_sum,
                actual_sum = EXCLUDED.actual_sum,
                forecast_sum = EXCLUDED.forecast_sum
            """
        ),
        {
            "model_run_id": model_run_id,
            "warehouse_id": warehouse_id,
            "sku_id": sku_id,
            **metrics,
        },
    )
    return len(records)


def run_forecasting(session: Session, model_run_id: int, horizon_days: int) -> tuple[int, list[str]]:
    transactions = _load_transactions(session)
    if transactions.empty:
        raise RuntimeError("No inventory transactions are available for forecasting")
    daily = prepare_daily_demand(transactions)
    forecast_rows = 0
    warnings: list[str] = []
    for (warehouse_id, sku_id), group in daily.groupby(["warehouse_id", "sku_id"], sort=False):
        result = forecast_group(
            group,
            horizon_days=horizon_days,
            min_training_days=settings.min_training_days,
        )
        forecast_rows += _store_forecast_result(
            session,
            model_run_id,
            int(warehouse_id),
            int(sku_id),
            result,
        )
        if result.warning:
            warnings.append(f"warehouse_id={warehouse_id}, sku_id={sku_id}: {result.warning}")
    session.commit()
    return forecast_rows, warnings


def _load_replenishment_base(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            WITH preferred_supplier AS (
                SELECT DISTINCT ON (ss.sku_id)
                    ss.sku_id,
                    ss.supplier_id,
                    sup.contractual_lead_time_days
                FROM inventory.supplier_sku ss
                JOIN inventory.dim_supplier sup ON sup.supplier_id = ss.supplier_id
                WHERE ss.active = TRUE AND sup.active = TRUE
                ORDER BY ss.sku_id, ss.priority_rank, ss.supplier_id
            )
            SELECT
                li.warehouse_id,
                li.sku_id,
                w.region,
                li.on_hand_qty,
                li.allocated_qty,
                li.on_order_qty,
                li.backorder_qty,
                li.inventory_position_qty,
                sku.minimum_order_qty,
                sku.order_multiple,
                ps.supplier_id,
                COALESCE(ps.contractual_lead_time_days, 7) AS contractual_lead_time_days
            FROM inventory.vw_latest_inventory li
            JOIN inventory.dim_warehouse w ON w.warehouse_id = li.warehouse_id AND w.active = TRUE
            JOIN inventory.dim_sku sku ON sku.sku_id = li.sku_id AND sku.active = TRUE
            LEFT JOIN preferred_supplier ps ON ps.sku_id = li.sku_id
            """
        )
    ).mappings()
    return [dict(row) for row in rows]


def _load_demand_statistics(session: Session) -> dict[tuple[int, int], dict[str, float]]:
    rows = session.execute(
        text(
            """
            WITH pairs AS (
                SELECT DISTINCT warehouse_id, sku_id
                FROM inventory.inventory_transactions
                WHERE transaction_type IN ('SALE','TRANSFER_OUT','DAMAGE')
                  AND transaction_ts >= CURRENT_DATE - INTERVAL '365 days'
            ),
            calendar AS (
                SELECT generate_series(
                    CURRENT_DATE - INTERVAL '89 days',
                    CURRENT_DATE,
                    INTERVAL '1 day'
                )::DATE AS demand_date
            ),
            daily AS (
                SELECT
                    warehouse_id,
                    sku_id,
                    transaction_ts::DATE AS demand_date,
                    SUM(ABS(quantity)) AS demand_qty
                FROM inventory.inventory_transactions
                WHERE transaction_type IN ('SALE','TRANSFER_OUT','DAMAGE')
                  AND transaction_ts >= CURRENT_DATE - INTERVAL '89 days'
                GROUP BY warehouse_id, sku_id, transaction_ts::DATE
            ),
            complete_daily AS (
                SELECT
                    p.warehouse_id,
                    p.sku_id,
                    c.demand_date,
                    COALESCE(d.demand_qty, 0) AS demand_qty
                FROM pairs p
                CROSS JOIN calendar c
                LEFT JOIN daily d
                  ON d.warehouse_id = p.warehouse_id
                 AND d.sku_id = p.sku_id
                 AND d.demand_date = c.demand_date
            )
            SELECT
                warehouse_id,
                sku_id,
                COALESCE(AVG(demand_qty), 0) AS avg_daily_demand,
                COALESCE(STDDEV_SAMP(demand_qty), 0) AS demand_stddev
            FROM complete_daily
            GROUP BY warehouse_id, sku_id
            """
        )
    ).mappings()
    return {
        (int(row["warehouse_id"]), int(row["sku_id"])): {
            "avg_daily_demand": float(row["avg_daily_demand"] or 0),
            "demand_stddev": float(row["demand_stddev"] or 0),
        }
        for row in rows
    }


def _load_lead_time_statistics(session: Session) -> dict[tuple[int, int, int | None], dict[str, float]]:
    rows = session.execute(
        text(
            """
            SELECT
                supplier_id,
                warehouse_id,
                sku_id,
                AVG(actual_lead_time_days) AS avg_lead_time_days,
                COALESCE(STDDEV_SAMP(actual_lead_time_days), 0) AS lead_time_stddev
            FROM inventory.supplier_lead_time_events
            WHERE receipt_date IS NOT NULL
              AND order_date >= CURRENT_DATE - INTERVAL '730 days'
            GROUP BY supplier_id, warehouse_id, sku_id
            """
        )
    ).mappings()
    return {
        (int(row["supplier_id"]), int(row["warehouse_id"]), int(row["sku_id"]) if row["sku_id"] is not None else None): {
            "avg_lead_time_days": float(row["avg_lead_time_days"] or 0),
            "lead_time_stddev": float(row["lead_time_stddev"] or 0),
        }
        for row in rows
    }


def _load_forecasts(session: Session, model_run_id: int) -> dict[tuple[int, int], list[tuple[date, float]]]:
    rows = session.execute(
        text(
            """
            SELECT warehouse_id, sku_id, forecast_date, forecast_qty
            FROM inventory.demand_forecasts
            WHERE model_run_id = :model_run_id
            ORDER BY warehouse_id, sku_id, forecast_date
            """
        ),
        {"model_run_id": model_run_id},
    ).mappings()
    result: dict[tuple[int, int], list[tuple[date, float]]] = defaultdict(list)
    for row in rows:
        result[(int(row["warehouse_id"]), int(row["sku_id"]))].append(
            (row["forecast_date"], float(row["forecast_qty"]))
        )
    return result


def _load_external_adjustments(session: Session) -> dict[str, dict[str, float | str]]:
    """Load the latest normalized operational signal for each region.

    Supported signal types:
    - DEMAND_MULTIPLIER: multiplies forecast and historical demand assumptions.
    - LEAD_TIME_PENALTY_DAYS: adds days to the supplier lead-time assumption.
    """
    rows = session.execute(
        text(
            """
            SELECT DISTINCT ON (region, signal_type)
                region, signal_type, signal_value, signal_date, source_name
            FROM inventory.external_signals
            WHERE signal_type IN ('DEMAND_MULTIPLIER', 'LEAD_TIME_PENALTY_DAYS')
              AND signal_date >= CURRENT_DATE - INTERVAL '7 days'
              AND signal_date <= CURRENT_DATE
            ORDER BY region, signal_type, signal_date DESC, ingested_at DESC
            """
        )
    ).mappings()
    result: dict[str, dict[str, float | str]] = defaultdict(dict)
    for row in rows:
        region = str(row["region"])
        if row["signal_type"] == "DEMAND_MULTIPLIER":
            result[region]["demand_multiplier"] = max(0.0, float(row["signal_value"]))
        elif row["signal_type"] == "LEAD_TIME_PENALTY_DAYS":
            result[region]["lead_time_penalty"] = max(0.0, float(row["signal_value"]))
        result[region][f"{str(row['signal_type']).lower()}_source"] = str(row["source_name"])
    return dict(result)


def _load_active_overrides(session: Session) -> dict[tuple[int, int], list[dict[str, Any]]]:
    rows = session.execute(
        text(
            """
            SELECT warehouse_id, sku_id, override_type, numeric_value, text_value, override_id
            FROM inventory.operational_overrides
            WHERE status = 'APPROVED'
              AND effective_from <= CURRENT_TIMESTAMP
              AND (effective_to IS NULL OR effective_to > CURRENT_TIMESTAMP)
            ORDER BY created_at, override_id
            """
        )
    ).mappings()
    result: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[(int(row["warehouse_id"]), int(row["sku_id"]))].append(dict(row))
    return result


def run_replenishment(session: Session, model_run_id: int) -> int:
    base_rows = _load_replenishment_base(session)
    demand_stats = _load_demand_statistics(session)
    lead_stats = _load_lead_time_statistics(session)
    forecasts = _load_forecasts(session, model_run_id)
    overrides = _load_active_overrides(session)
    external_adjustments = _load_external_adjustments(session)

    records: list[dict[str, Any]] = []
    for base in base_rows:
        key = (int(base["warehouse_id"]), int(base["sku_id"]))
        future_forecast = forecasts.get(key, [])
        if not future_forecast:
            continue
        demand = demand_stats.get(key, {"avg_daily_demand": 0.0, "demand_stddev": 0.0})
        base, demand, future_forecast, controls = apply_adjustments(
            base,
            demand,
            future_forecast,
            overrides.get(key, []),
            external_adjustments.get(str(base["region"]), {}),
        )
        supplier_id = int(base["supplier_id"]) if base["supplier_id"] is not None else None
        historical = None
        if supplier_id is not None:
            historical = lead_stats.get((supplier_id, key[0], key[1])) or lead_stats.get((supplier_id, key[0], None))
        avg_lead_time = (
            float(historical["avg_lead_time_days"])
            if historical and historical["avg_lead_time_days"] > 0
            else float(base["contractual_lead_time_days"])
        ) + float(controls["lead_time_penalty"])
        lead_stddev = float(historical["lead_time_stddev"]) if historical else 0.0

        inputs = ReplenishmentInputs(
            service_level=settings.default_service_level,
            avg_daily_demand=float(demand["avg_daily_demand"]),
            demand_stddev=float(demand["demand_stddev"]),
            avg_lead_time_days=max(0.0, avg_lead_time),
            lead_time_stddev=max(0.0, lead_stddev),
            inventory_position=float(base["inventory_position_qty"]),
            minimum_order_qty=float(base["minimum_order_qty"]),
            order_multiple=float(base["order_multiple"]),
            review_period_days=7.0,
        )
        result = calculate_replenishment(inputs, future_forecast, as_of_date=date.today())
        safety_stock = result.safety_stock
        reorder_point = result.reorder_point
        target_stock = result.target_stock
        recommended_order = result.recommended_order_qty
        if controls["safety_stock_override"] is not None:
            safety_stock = float(controls["safety_stock_override"])
            reorder_point = inputs.avg_daily_demand * inputs.avg_lead_time_days + safety_stock
            target_stock = inputs.avg_daily_demand * (inputs.avg_lead_time_days + inputs.review_period_days) + safety_stock
            recommended_order = round_order_quantity(
                max(0.0, target_stock - inputs.inventory_position),
                inputs.minimum_order_qty,
                inputs.order_multiple,
            )
        if controls["reorder_qty_override"] is not None:
            recommended_order = round_order_quantity(
                float(controls["reorder_qty_override"]),
                inputs.minimum_order_qty,
                inputs.order_multiple,
            )
        if controls["hold_replenishment"]:
            recommended_order = 0.0

        details = dict(result.details)
        details.update(controls)
        records.append(
            {
                "model_run_id": model_run_id,
                "recommendation_date": date.today(),
                "warehouse_id": key[0],
                "sku_id": key[1],
                "supplier_id": supplier_id,
                "service_level": inputs.service_level,
                "avg_daily_demand": inputs.avg_daily_demand,
                "demand_stddev": inputs.demand_stddev,
                "avg_lead_time_days": inputs.avg_lead_time_days,
                "lead_time_stddev": inputs.lead_time_stddev,
                "safety_stock_qty": safety_stock,
                "reorder_point_qty": reorder_point,
                "target_stock_qty": target_stock,
                "inventory_position_qty": inputs.inventory_position,
                "gross_recommended_order_qty": recommended_order,
                "recommended_order_qty": recommended_order,
                "expected_stockout_date": result.expected_stockout_date,
                "risk_band": result.risk_band,
                "calculation_details": json.dumps(details),
            }
        )

    if records:
        session.execute(
            text(
                """
                INSERT INTO inventory.replenishment_recommendations
                    (model_run_id, recommendation_date, warehouse_id, sku_id, supplier_id,
                     service_level, avg_daily_demand, demand_stddev, avg_lead_time_days,
                     lead_time_stddev, safety_stock_qty, reorder_point_qty, target_stock_qty,
                     inventory_position_qty, gross_recommended_order_qty, recommended_order_qty,
                     expected_stockout_date, risk_band, calculation_details)
                VALUES
                    (:model_run_id, :recommendation_date, :warehouse_id, :sku_id, :supplier_id,
                     :service_level, :avg_daily_demand, :demand_stddev, :avg_lead_time_days,
                     :lead_time_stddev, :safety_stock_qty, :reorder_point_qty, :target_stock_qty,
                     :inventory_position_qty, :gross_recommended_order_qty, :recommended_order_qty,
                     :expected_stockout_date, :risk_band, CAST(:calculation_details AS JSONB))
                ON CONFLICT (model_run_id, recommendation_date, warehouse_id, sku_id) DO UPDATE SET
                    supplier_id = EXCLUDED.supplier_id,
                    service_level = EXCLUDED.service_level,
                    avg_daily_demand = EXCLUDED.avg_daily_demand,
                    demand_stddev = EXCLUDED.demand_stddev,
                    avg_lead_time_days = EXCLUDED.avg_lead_time_days,
                    lead_time_stddev = EXCLUDED.lead_time_stddev,
                    safety_stock_qty = EXCLUDED.safety_stock_qty,
                    reorder_point_qty = EXCLUDED.reorder_point_qty,
                    target_stock_qty = EXCLUDED.target_stock_qty,
                    inventory_position_qty = EXCLUDED.inventory_position_qty,
                    gross_recommended_order_qty = EXCLUDED.gross_recommended_order_qty,
                    recommended_order_qty = EXCLUDED.recommended_order_qty,
                    expected_stockout_date = EXCLUDED.expected_stockout_date,
                    risk_band = EXCLUDED.risk_band,
                    calculation_details = EXCLUDED.calculation_details,
                    created_at = CURRENT_TIMESTAMP
                """
            ),
            records,
        )
    session.commit()
    return len(records)


def run_full_pipeline(horizon_days: int | None = None) -> dict[str, Any]:
    horizon_days = horizon_days or settings.forecast_horizon_days
    started_at = _utc_now()
    model_run_id: int | None = None
    warnings: list[str] = []

    with SessionLocal() as session:
        model_run_id = _create_model_run(session, horizon_days)

    try:
        with SessionLocal() as session:
            forecast_rows, forecast_warnings = run_forecasting(session, model_run_id, horizon_days)
            warnings.extend(forecast_warnings)
            recommendation_rows = run_replenishment(session, model_run_id)
            transfer_rows = run_network_rebalancing(session, model_run_id)
            session.execute(
                text(
                    """
                    UPDATE inventory.model_runs
                    SET training_start_date = (
                            SELECT MIN(transaction_ts)::DATE FROM inventory.inventory_transactions
                        ),
                        training_end_date = (
                            SELECT MAX(transaction_ts)::DATE FROM inventory.inventory_transactions
                        )
                    WHERE model_run_id = :model_run_id
                    """
                ),
                {"model_run_id": model_run_id},
            )
            session.commit()
            _finish_model_run(session, model_run_id, "SUCCEEDED")
    except Exception as exc:
        logger.exception("Pipeline failed for model_run_id=%s", model_run_id)
        with SessionLocal() as failure_session:
            _finish_model_run(failure_session, model_run_id, "FAILED", str(exc)[:4000])
        raise

    finished_at = _utc_now()
    return {
        "model_run_id": model_run_id,
        "forecast_rows": forecast_rows,
        "recommendation_rows": recommendation_rows,
        "transfer_recommendation_rows": transfer_rows,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "warnings": warnings,
    }

"""Train, compare, persist, and select models from measured time-based results."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.forecasting.base_model import ForecastModel
from decision_intelligence.forecasting.lightgbm_model import LightGBMForecastModel
from decision_intelligence.forecasting.metrics import calculate_metrics
from decision_intelligence.forecasting.seasonal_naive import SeasonalNaiveModel
from decision_intelligence.forecasting.xgboost_model import XGBoostForecastModel
from decision_intelligence.settings import DatabaseSettings

MODEL_FEATURES = [
    "product_code", "store_code", "day_of_week", "day_of_month", "week_of_year",
    "month", "quarter", "weekend_flag", "event_flag", "event_type_code", "snap_flag",
    "lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14", "rolling_std_7",
    "current_price", "price_lag_7", "price_change_percentage", "relative_price_to_category",
    "promotion_proxy", "current_stock", "days_of_supply", "open_purchase_order_quantity",
    "expected_inbound_quantity", "supplier_lead_time", "safety_stock", "reorder_point",
    "stockout_flag",
]


def _normalise(series: pd.Series) -> pd.Series:
    spread = series.max() - series.min()
    return pd.Series(0.0, index=series.index) if spread == 0 else (series - series.min()) / spread


def _persist_run(
    settings: DatabaseSettings,
    model: ForecastModel,
    run_id: uuid.UUID,
    started: datetime,
    completed: datetime,
    training_rows: int,
    training_time: float,
    inference_time: float,
    artifact_path: str,
    metrics: dict[str, float],
) -> int:
    with connect(settings) as connection:
        connection.execute(
            """IF COL_LENGTH('dbo.FactForecastMetric','SMAPE') IS NULL
            ALTER TABLE dbo.FactForecastMetric ADD SMAPE decimal(19,8) NULL"""
        )
        connection.execute(
            """EXEC(N'CREATE OR ALTER VIEW dbo.vw_ModelPerformance AS
            SELECT fm.ForecastMetricKey,m.ModelID,m.ModelName,m.ModelVersion,
              mr.ModelRunID,mr.RunStatus,mr.TrainingTimeSeconds,mr.InferenceTimeSeconds,
              p.ProductID,c.CategoryID,fm.HorizonDays,fm.FoldNumber,
              fm.WAPE,fm.RMSE,fm.MAE,fm.Bias,fm.SMAPE,fm.MASE,fm.RMSSE,fm.Coverage
            FROM dbo.FactForecastMetric fm JOIN dbo.DimModel m ON m.ModelKey=fm.ModelKey
            JOIN dbo.FactModelRun mr ON mr.ModelRunKey=fm.ModelRunKey
            LEFT JOIN dbo.DimProduct p ON p.ProductKey=fm.ProductKey
            LEFT JOIN dbo.DimCategory c ON c.CategoryKey=fm.CategoryKey')"""
        )
        model_key = int(fetch_scalar(
            connection, "SELECT ModelKey FROM dbo.DimModel WHERE ModelID=?", model.model_id
        ))
        row = connection.execute(
            """INSERT dbo.FactModelRun
            (ModelRunID,ModelKey,RunStartedAt,RunCompletedAt,RunStatus,ParametersJson,
             TrainingRows,TrainingTimeSeconds,InferenceTimeSeconds,ArtifactPath,
             PipelineRunID,SourceSystem,DataVersion)
            OUTPUT INSERTED.ModelRunKey VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            run_id, model_key, started, completed, "SUCCEEDED",
            json.dumps(model.parameters(), sort_keys=True, default=str), training_rows,
            training_time, inference_time, artifact_path, run_id,
            "FORECAST_TRAINING", "phase-9-v1",
        ).fetchone()
        if row is None:
            raise RuntimeError("Model run insert returned no key")
        model_run_key = int(row[0])
        connection.execute(
            """INSERT dbo.FactForecastMetric
            (ModelRunKey,ModelKey,HorizonDays,FoldNumber,WAPE,RMSE,MAE,Bias,SMAPE,
             PipelineRunID,SourceSystem,DataVersion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            model_run_key, model_key, 7, 1, metrics["wape"], metrics["rmse"],
            metrics["mae"], metrics["bias"], metrics["smape"], run_id,
            "FORECAST_TRAINING", "phase-9-v1",
        )
        connection.commit()
    return model_run_key


def train_compare_select(
    settings: DatabaseSettings,
    feature_path: Path,
    project_root: Path,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Train all required models on one temporal split and select by weighted evidence."""
    frame = pd.read_parquet(feature_path).sort_values("date")
    eligible = frame.dropna(subset=["lag_1", "lag_7", "lag_14", "rolling_mean_7"])
    dates = sorted(pd.to_datetime(eligible["date"]).unique())
    if len(dates) < 8:
        raise RuntimeError("At least eight eligible dates are required for time evaluation")
    test_dates = set(dates[-7:])
    train = eligible[~pd.to_datetime(eligible["date"]).isin(test_dates)].copy()
    test = eligible[pd.to_datetime(eligible["date"]).isin(test_dates)].copy()
    if train.empty or test.empty or train["date"].max() >= test["date"].min():
        raise RuntimeError("Invalid chronological train/test split")
    models: list[ForecastModel] = [
        SeasonalNaiveModel(), XGBoostForecastModel(seed), LightGBMForecastModel(seed)
    ]
    artifact_dir = project_root / "models" / "artifacts"
    metadata_dir = project_root / "models" / "metadata"
    report_dir = project_root / "reports" / "model_evaluation"
    for directory in (artifact_dir, metadata_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    run_keys: dict[str, int] = {}
    for model in models:
        started = datetime.now(UTC)
        timer = time.perf_counter()
        model.fit(train, MODEL_FEATURES)
        training_time = time.perf_counter() - timer
        timer = time.perf_counter()
        predicted = model.predict(test, MODEL_FEATURES)
        inference_time = time.perf_counter() - timer
        completed = datetime.now(UTC)
        metrics = calculate_metrics(test["target"].to_numpy(), predicted)
        run_id = uuid.uuid4()
        artifact_path = artifact_dir / f"{model.model_id.lower()}_{run_id}.joblib"
        artifact_reference = artifact_path.relative_to(project_root)
        joblib.dump({"model": model, "features": MODEL_FEATURES}, artifact_path)
        run_keys[model.model_id] = _persist_run(
            settings, model, run_id, started, completed, len(train), training_time,
            inference_time, artifact_reference.as_posix(), metrics,
        )
        results.append({
            "model_id": model.model_id, "model_name": model.model_name,
            **metrics, "training_time": training_time, "inference_time": inference_time,
            "artifact_path": artifact_reference.as_posix(), "model_run_id": str(run_id),
        })
        predictions = test[
            ["date", "product_id", "category_id", "store_id", "target"]
        ].copy()
        predictions["prediction"] = predicted
        predictions["model_id"] = model.model_id
        prediction_frames.append(predictions)
    comparison = pd.DataFrame(results)
    comparison["selection_score"] = (
        0.50 * _normalise(comparison["wape"].astype(float))
        + 0.20 * _normalise(comparison["bias"].abs().astype(float))
        + 0.10 * _normalise(comparison["inference_time"].astype(float))
        + 0.20 * _normalise(comparison["residual_std"].astype(float))
    )
    comparison = comparison.sort_values(
        ["selection_score", "wape", "model_id"]
    ).reset_index(drop=True)
    winner = comparison.iloc[0]
    selected = {
        "model_id": str(winner["model_id"]), "model_name": str(winner["model_name"]),
        "artifact_path": str(winner["artifact_path"]),
        "model_run_key": run_keys[str(winner["model_id"])],
        "wape": float(winner["wape"]), "bias": float(winner["bias"]),
        "residual_std": float(winner["residual_std"]),
        "selected_at": datetime.now(UTC).isoformat(),
        "reason": "Lowest configured weighted score from measured holdout results.",
    }
    comparison.to_csv(report_dir / "model_comparison.csv", index=False)
    all_predictions = pd.concat(prediction_frames, ignore_index=True)
    all_predictions.to_parquet(report_dir / "holdout_predictions.parquet", index=False)
    for prediction_model_id, predictions in all_predictions.groupby("model_id"):
        predictions.to_csv(
            report_dir / f"{str(prediction_model_id).lower()}_predictions.csv", index=False
        )
    category_rows: list[dict[str, object]] = []
    for (category_model_id, category_id), group in all_predictions.groupby(
        ["model_id", "category_id"]
    ):
        category_rows.append({
            "model_id": category_model_id,
            "category_id": category_id,
            **calculate_metrics(group["target"].to_numpy(), group["prediction"].to_numpy()),
        })
    pd.DataFrame(category_rows).to_csv(report_dir / "category_errors.csv", index=False)
    comparison[["model_id", "bias"]].to_csv(report_dir / "forecast_bias.csv", index=False)
    _write_metric_chart(comparison, report_dir / "metric_comparison.svg")
    (report_dir / "winner_explanation.md").write_text(
        "# Production model selection\n\n"
        f"**Winner:** {selected['model_name']} (`{selected['model_id']}`)\n\n"
        f"Measured WAPE: {selected['wape']:.4f}; bias: {selected['bias']:.4f}. "
        "The winner has the lowest configured weighted score using WAPE, absolute bias, "
        "inference time, and residual variability. No model name is privileged.\n",
        encoding="utf-8",
    )
    (metadata_dir / "selected_model.json").write_text(
        json.dumps(selected, indent=2), encoding="utf-8"
    )
    with connect(settings) as connection:
        connection.execute("UPDATE dbo.DimModel SET IsProduction=0")
        connection.execute(
            "UPDATE dbo.DimModel SET IsProduction=1 WHERE ModelID=?", selected["model_id"]
        )
        connection.commit()
    return comparison, selected


def _write_metric_chart(comparison: pd.DataFrame, path: Path) -> None:
    """Write a dependency-free SVG comparison chart from measured WAPE values."""
    width, height, margin = 720, 360, 70
    usable_width = width - 2 * margin
    max_wape = max(float(comparison["wape"].max()), 0.01)
    bar_width = usable_width / max(len(comparison), 1) * 0.55
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="360" y="28" text-anchor="middle" font-family="sans-serif" '
        'font-size="18">Holdout WAPE by model (lower is better)</text>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" '
        f'y2="{height-margin}" stroke="#333"/>',
    ]
    for index, row in enumerate(comparison.to_dict(orient="records")):
        value = float(row["wape"])
        x = margin + (index + 0.5) * usable_width / len(comparison) - bar_width / 2
        bar_height = (height - 2 * margin) * value / max_wape
        y = height - margin - bar_height
        color = "#2563eb" if index == 0 else "#94a3b8"
        parts.extend([
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}" fill="{color}"/>',
            f'<text x="{x + bar_width/2:.1f}" y="{y-8:.1f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="13">{value:.3f}</text>',
            f'<text x="{x + bar_width/2:.1f}" y="{height-margin+22}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="12">{row["model_id"]}</text>',
        ])
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")

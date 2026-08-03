"""SHAP-based tree explanations with an auditable seasonal-naive fallback."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from decision_intelligence.database.connection import connect
from decision_intelligence.explainability.explanation_writer import explanation_text
from decision_intelligence.settings import DatabaseSettings


def _contributions(
    model_id: str,
    model: Any,
    frame: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, list[str], str]:
    if model_id in {"XGBOOST", "LIGHTGBM"}:
        import shap

        values = np.asarray(shap.TreeExplainer(model.model).shap_values(frame[features]))
        return values, features, "SHAP"
    values = np.zeros((len(frame), 1), dtype=float)
    values[:, 0] = frame["lag_7"].to_numpy(dtype=float)
    return values, ["lag_7"], "SEASONAL_COMPONENT"


def generate_explanations(
    settings: DatabaseSettings,
    forecast_path: Path,
    metadata_path: Path,
    output_path: Path,
    top_n: int = 5,
) -> pd.DataFrame:
    """Compute, rank, export, and upsert local explanations for every forecast."""
    frame = pd.read_parquet(forecast_path)
    selected = json.loads(metadata_path.read_text(encoding="utf-8"))
    artifact_path = Path(selected["artifact_path"])
    if not artifact_path.is_absolute():
        artifact_path = metadata_path.resolve().parents[2] / artifact_path
    payload = joblib.load(artifact_path)
    model, model_features = payload["model"], payload["features"]
    values, explanation_features, method = _contributions(
        selected["model_id"], model, frame, model_features
    )
    rows: list[dict[str, Any]] = []
    for index, forecast in enumerate(frame.to_dict(orient="records")):
        ordering = np.argsort(np.abs(values[index]))[::-1][:top_n]
        for rank, feature_index in enumerate(ordering, start=1):
            feature = explanation_features[int(feature_index)]
            contribution = float(values[index, feature_index])
            feature_value = forecast[feature]
            rows.append({
                "forecast_id": forecast["forecast_id"],
                "feature_name": feature,
                "feature_value": str(feature_value),
                "shap_value": contribution,
                "contribution_rank": rank,
                "direction": (
                    "POSITIVE" if contribution > 0
                    else "NEGATIVE" if contribution < 0
                    else "NEUTRAL"
                ),
                "explanation_text": explanation_text(feature, feature_value, contribution),
                "explanation_method": method,
            })
    result = pd.DataFrame(rows)
    pipeline_id = uuid.uuid4()
    with connect(settings) as connection:
        forecast_keys = {
            str(row[0]).lower(): int(row[1])
            for row in connection.execute("SELECT ForecastID,ForecastKey FROM dbo.FactForecast")
        }
        sql_rows = [(
            forecast_keys[str(row["forecast_id"]).lower()], row["feature_name"],
            str(row["feature_value"])[:200], float(row["shap_value"]),
            int(row["contribution_rank"]), row["direction"], row["explanation_text"],
            pipeline_id, f"FORECAST_{row['explanation_method']}", "phase-10-v1",
        ) for row in result.to_dict(orient="records")]
        connection.cursor().executemany(
            """MERGE dbo.FactModelExplanation AS target
            USING (SELECT ? ForecastKey,? ContributionRank) AS source
            ON target.ForecastKey=source.ForecastKey
              AND target.ContributionRank=source.ContributionRank
            WHEN MATCHED THEN UPDATE SET FeatureName=?,FeatureValue=?,ShapValue=?,
              Direction=?,ExplanationText=?,UpdatedAt=SYSUTCDATETIME(),PipelineRunID=?,
              SourceSystem=?,DataVersion=?
            WHEN NOT MATCHED THEN INSERT
              (ForecastKey,FeatureName,FeatureValue,ShapValue,ContributionRank,Direction,
               ExplanationText,PipelineRunID,SourceSystem,DataVersion)
              VALUES (source.ForecastKey,?,?,?,?,?,?,?,?,?);""",
            [(
                row[0], row[4], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9],
                row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9],
            ) for row in sql_rows],
        )
        connection.commit()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False)
    result.to_csv(output_path.with_suffix(".csv"), index=False)
    return result

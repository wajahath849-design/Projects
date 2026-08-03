"""Database verification for the completed Phase 5-10 sample pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_feature_dataset_has_stable_unique_grain() -> None:
    frame = pd.read_parquet(
        PROJECT_ROOT / "data" / "processed" / "features" / "sample_features.parquet"
    )
    assert len(frame) == 224
    assert frame[["product_id", "store_id", "date"]].drop_duplicates().shape[0] == 224
    assert frame[["lag_1", "lag_7", "lag_14", "rolling_mean_7"]].notna().all(axis=1).sum() == 112


def test_models_metrics_and_production_selection_are_persisted() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        assert int(fetch_scalar(
            connection, "SELECT COUNT(*) FROM dbo.DimModel WHERE IsProduction=1"
        )) == 1
        stored = connection.execute(
            """SELECT COUNT(DISTINCT m.ModelID),COUNT(fm.SMAPE)
            FROM dbo.FactForecastMetric fm
            JOIN dbo.DimModel m ON m.ModelKey=fm.ModelKey
            WHERE fm.SourceSystem='FORECAST_TRAINING'"""
        ).fetchone()
        assert stored is not None
        assert int(stored[0]) == 3
        assert int(stored[1]) >= 3


def test_forecast_and_shap_grains_are_complete() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        horizon_counts = dict(connection.execute(
            """SELECT HorizonDays,COUNT(*) FROM dbo.FactForecast
            WHERE DataVersion='phase-10-v1' GROUP BY HorizonDays"""
        ).fetchall())
        assert horizon_counts == {7: 56, 30: 184, 90: 480}
        invalid = int(fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactForecast WHERE DataVersion='phase-10-v1'
            AND (ForecastQuantity<0 OR LowerBound<0 OR UpperBound<LowerBound
              OR ForecastConfidence NOT BETWEEN 0 AND 1)""",
        ))
        assert invalid == 0
        explanations = connection.execute(
            """SELECT COUNT(*),COUNT(DISTINCT ForecastKey),MIN(ContributionRank),
              MAX(ContributionRank) FROM dbo.FactModelExplanation
            WHERE DataVersion='phase-10-v1'"""
        ).fetchone()
        assert explanations is not None
        assert tuple(map(int, explanations)) == (3600, 720, 1, 5)

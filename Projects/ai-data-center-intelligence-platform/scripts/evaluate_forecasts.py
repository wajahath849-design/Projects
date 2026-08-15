from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.forecasting import METRICS, MetricForecaster


def confidence(r_squared: float) -> str:
    if r_squared >= 0.8:
        return "high_trend_fit"
    if r_squared >= 0.5:
        return "moderate_trend_fit"
    return "low_trend_fit"


def main() -> None:
    forecaster = MetricForecaster(settings.database_path)
    target_year = forecaster.latest_complete_year() + 5
    results = []
    for metric in METRICS:
        output = forecaster.forecast(metric, target_year)
        overall = output.frame.iloc[0]
        results.append({
            "metric": metric.key,
            "display_name": metric.display_name,
            "unit": metric.unit,
            "target_year": target_year,
            "predicted_value": float(overall["predicted_value"]),
            "lower_95": float(overall["lower_95"]),
            "upper_95": float(overall["upper_95"]),
            "r_squared": float(overall["r_squared"]),
            "backtest_mae": float(overall["backtest_mae"]),
            "confidence": confidence(float(overall["r_squared"])),
            "training_start_year": int(overall["training_start_year"]),
            "training_end_year": int(overall["training_end_year"]),
        })
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": "synthetic data modeling realistic data-center operations",
        "method": "annual ordinary least squares linear trend",
        "interval": "approximate 95% prediction interval",
        "target_year": target_year,
        "metric_count": len(results),
        "results": results,
    }
    target = PROJECT_ROOT / "docs/forecast_validation.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"target_year": target_year, "metric_count": len(results), "output": str(target)}, indent=2))


if __name__ == "__main__":
    main()

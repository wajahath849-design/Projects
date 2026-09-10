"""Independent cost/carbon reconciliation for the advanced release audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.sustainability.engine import CostCarbonEngine


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "evaluation/results/cost_carbon_validation_phase_l.json"


def run_validation(result_path: Path = RESULT) -> dict[str, object]:
    power = pd.read_csv(ROOT / "data/processed/power_metrics.csv")
    power["timestamp"] = pd.to_datetime(power["timestamp"])
    power = power[power["timestamp"].dt.year == 2025].copy()
    prices = pd.read_csv(ROOT / "data/assumptions/energy_prices.csv")
    carbon = pd.read_csv(ROOT / "data/assumptions/carbon_intensity.csv")
    for frame in (prices, carbon):
        frame["effective_from"] = pd.to_datetime(frame["effective_from"])
        frame["effective_to"] = pd.to_datetime(frame["effective_to"])
    joined = power.merge(prices, on="facility_id", validate="many_to_many")
    joined = joined[
        joined["timestamp"].between(joined["effective_from"], joined["effective_to"])
    ].copy()
    joined = joined.merge(
        carbon, on="facility_id", suffixes=("_price", "_carbon"), validate="many_to_many"
    )
    joined = joined[
        joined["timestamp"].between(
            joined["effective_from_carbon"], joined["effective_to_carbon"]
        )
    ].copy()
    joined["modeled_energy_kwh"] = joined["power_draw_kw"] * 24
    joined["modeled_cooling_energy_kwh"] = joined["cooling_power_kw"] * 24
    joined["modeled_energy_cost_usd"] = (
        joined["modeled_energy_kwh"] * joined["price_per_kwh"]
    )
    joined["modeled_cooling_cost_usd"] = (
        joined["modeled_cooling_energy_kwh"] * joined["price_per_kwh"]
    )
    joined["modeled_carbon_tonnes"] = (
        joined["modeled_energy_kwh"] * joined["grams_co2e_per_kwh"] / 1_000_000
    )

    engine = CostCarbonEngine(
        ROOT / "database/datacenter.db",
        ROOT / "data/assumptions/energy_prices.csv",
        ROOT / "data/assumptions/carbon_intensity.csv",
        ROOT / "analytics/efficiency_opportunity_weights.yaml",
    )
    actual = engine.summarize("2025-01-01", "2025-12-31")
    metric_names = [
        "modeled_energy_kwh", "modeled_energy_cost_usd",
        "modeled_cooling_cost_usd", "modeled_carbon_tonnes",
    ]
    metrics = {}
    for name in metric_names:
        expected = float(joined[name].sum())
        observed = float(actual.totals[name])
        metrics[name] = {
            "independent_value": expected,
            "engine_value": observed,
            "passed": bool(np.isclose(expected, observed, rtol=1e-10, atol=1e-6)),
        }
    scenario = engine.efficiency_scenario(10, year=2025)
    forecast = engine.forecast(2030).frame
    checks = {
        "date_effective_coverage": len(joined) == len(power),
        "currency_is_declared": set(joined["currency"]) == {"USD"},
        "cost_metrics_reconcile": all(item["passed"] for item in metrics.values()),
        "opportunity_score_bounded": actual.frame[
            "efficiency_opportunity_score"
        ].between(0, 100).all(),
        "scenario_unit_math": np.isclose(
            scenario["energy_savings_kwh"].sum(),
            joined["modeled_cooling_energy_kwh"].sum() * 0.10,
        ),
        "forecast_cost_formula": np.allclose(
            forecast["projected_energy_cost_usd"],
            forecast["modeled_energy_kwh"] * forecast["projected_price_per_kwh"],
        ),
        "forecast_carbon_conversion": np.allclose(
            forecast["projected_carbon_tonnes"],
            forecast["modeled_energy_kwh"]
            * forecast["projected_carbon_intensity_g_per_kwh"] / 1_000_000,
        ),
        "synthetic_assumptions_labeled": (
            forecast["assumptions_are_synthetic"].all()
            and joined["is_synthetic_price"].all()
            and joined["is_synthetic_carbon"].all()
        ),
    }
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "independent 2025 cost/carbon reconciliation plus 2030 formula checks",
        "metrics": metrics,
        "checks": {name: bool(value) for name, value in checks.items()},
        "all_passed": all(checks.values()),
        "caveat": "All price and carbon factors are configured synthetic assumptions.",
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = run_validation()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_passed"] else 1)

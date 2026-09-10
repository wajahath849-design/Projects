from pathlib import Path

import numpy as np

from src.sustainability.engine import CostCarbonEngine


ROOT = Path(__file__).resolve().parents[1]


def engine() -> CostCarbonEngine:
    return CostCarbonEngine(
        ROOT / "database/datacenter.db",
        ROOT / "data/assumptions/energy_prices.csv",
        ROOT / "data/assumptions/carbon_intensity.csv",
        ROOT / "analytics/efficiency_opportunity_weights.yaml",
    )


def test_units_and_cost_carbon_formulas_are_exact() -> None:
    frame = engine().daily_model("2025-01-01", "2025-01-01", ["DC-FRA-01"])
    assert len(frame) == 1
    row = frame.iloc[0]
    assert np.isclose(row["modeled_energy_kwh"], row["power_draw_kw"] * 24)
    assert np.isclose(row["modeled_energy_cost_usd"], row["modeled_energy_kwh"] * row["price_per_kwh"])
    assert np.isclose(row["modeled_carbon_tonnes"], row["modeled_energy_kwh"] * row["grams_co2e_per_kwh"] / 1_000_000)
    assert bool(row["price_is_synthetic"])
    assert bool(row["carbon_is_synthetic"])


def test_facility_totals_components_and_denominators_reconcile() -> None:
    result = engine().summarize("2025-01-01", "2025-12-31")
    assert len(result.frame) == 6
    assert np.isclose(result.frame["modeled_energy_cost_usd"].sum(), result.totals["modeled_energy_cost_usd"])
    assert (result.frame["server_count"] > 0).all()
    assert result.frame["efficiency_opportunity_score"].between(0, 100).all()
    assert len(result.assumptions) == 6
    assert all(item["price_is_synthetic"] for item in result.assumptions)


def test_forecast_and_efficiency_scenario_are_labeled_and_directional() -> None:
    forecast = engine().forecast(2030)
    assert len(forecast.frame) == 6
    assert forecast.frame["is_projection"].all()
    assert forecast.frame["assumptions_are_synthetic"].all()
    scenario = engine().efficiency_scenario(10, year=2025)
    assert (scenario["energy_savings_kwh"] > 0).all()
    assert (scenario["cost_savings_usd"] > 0).all()
    assert (scenario["avoided_carbon_tonnes"] > 0).all()
    assert (scenario["scenario_pue"] < scenario["baseline_pue"]).all()


def test_assumption_dates_have_no_overlaps_per_facility() -> None:
    for assumptions in (engine().energy_prices, engine().carbon_factors):
        for _, rows in assumptions.sort_values("effective_from").groupby("facility_id"):
            ends = rows["effective_to"].iloc[:-1].to_numpy()
            starts = rows["effective_from"].iloc[1:].to_numpy()
            assert all(end < start for end, start in zip(ends, starts))

"""Deterministic cost and carbon calculations over canonical power history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.database import connect_read_only


@dataclass(frozen=True)
class PortfolioSummary:
    frame: pd.DataFrame
    totals: dict[str, float]
    assumptions: tuple[dict[str, object], ...]
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class SustainabilityForecast:
    target_year: int
    frame: pd.DataFrame
    method: str
    training_period: str
    caveats: tuple[str, ...]


class CostCarbonEngine:
    """Calculate modeled energy, cost, carbon and opportunity without an LLM."""

    HOURS_PER_DAILY_OBSERVATION = 24.0
    GRAMS_PER_TONNE = 1_000_000.0

    def __init__(
        self,
        database_path: Path | str,
        energy_price_path: Path | str,
        carbon_intensity_path: Path | str,
        efficiency_weights_path: Path | str,
    ) -> None:
        self.database_path = Path(database_path)
        self.energy_prices = self._load_assumptions(
            energy_price_path,
            required={"facility_id", "effective_from", "effective_to", "price_per_kwh", "currency", "annual_escalation_pct", "source_label", "is_synthetic"},
        )
        self.carbon_factors = self._load_assumptions(
            carbon_intensity_path,
            required={"facility_id", "effective_from", "effective_to", "grams_co2e_per_kwh", "methodology", "annual_change_pct", "source_label", "is_synthetic"},
        )
        config = yaml.safe_load(Path(efficiency_weights_path).read_text(encoding="utf-8"))
        self.weight_version = str(config["version"])
        self.weights = {key: float(value) for key, value in config["weights"].items()}
        if set(self.weights) != {"pue", "cooling_cost_per_it_kwh", "carbon_intensity", "incident_rate"}:
            raise ValueError("Efficiency weights do not match the governed components")
        if not np.isclose(sum(self.weights.values()), 1.0):
            raise ValueError("Efficiency opportunity weights must sum to one")
        self.guardrails = tuple(str(value) for value in config["guardrails"])

    @staticmethod
    def _load_assumptions(path: Path | str, required: set[str]) -> pd.DataFrame:
        frame = pd.read_csv(path)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Missing assumption columns: {sorted(missing)}")
        frame["effective_from"] = pd.to_datetime(frame["effective_from"])
        frame["effective_to"] = pd.to_datetime(frame["effective_to"])
        if (frame["effective_to"] < frame["effective_from"]).any():
            raise ValueError("Assumption effective periods are invalid")
        return frame

    def _power_rows(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        facility_ids: list[str] | tuple[str, ...] | None = None,
    ) -> pd.DataFrame:
        sql = """SELECT p.facility_id, f.facility_name, p.timestamp,
            p.power_draw_kw, p.it_load_kw, p.cooling_power_kw, p.pue
            FROM power_metrics AS p JOIN facilities AS f USING (facility_id)
            WHERE 1=1"""
        params: list[object] = []
        if start_date:
            sql += " AND p.timestamp>=?"
            params.append(start_date)
        if end_date:
            sql += " AND p.timestamp<=?"
            params.append(end_date)
        if facility_ids:
            sql += f" AND p.facility_id IN ({','.join('?' for _ in facility_ids)})"
            params.extend(facility_ids)
        sql += " ORDER BY p.timestamp, p.facility_id"
        with connect_read_only(self.database_path) as connection:
            frame = pd.read_sql_query(sql, connection, params=params)
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        return frame

    @staticmethod
    def _effective_join(
        facts: pd.DataFrame, assumptions: pd.DataFrame, value_columns: list[str]
    ) -> pd.DataFrame:
        candidates = facts.merge(assumptions, on="facility_id", how="left", validate="many_to_many")
        valid = candidates[
            (candidates["timestamp"] >= candidates["effective_from"])
            & (candidates["timestamp"] <= candidates["effective_to"])
        ].copy()
        keys = ["facility_id", "timestamp"]
        if valid.duplicated(keys).any():
            raise ValueError("Overlapping date-effective assumptions found")
        if len(valid) != len(facts):
            raise ValueError("Every facility-day must resolve to exactly one governed assumption")
        return valid[[*facts.columns, *value_columns]]

    def daily_model(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        facility_ids: list[str] | tuple[str, ...] | None = None,
    ) -> pd.DataFrame:
        facts = self._power_rows(start_date, end_date, facility_ids)
        if facts.empty:
            return facts
        priced = self._effective_join(
            facts, self.energy_prices,
            ["price_per_kwh", "currency", "pricing_basis", "annual_escalation_pct", "source_label", "is_synthetic"],
        ).rename(columns={"source_label": "price_source", "is_synthetic": "price_is_synthetic"})
        joined = self._effective_join(
            priced, self.carbon_factors,
            ["grams_co2e_per_kwh", "methodology", "annual_change_pct", "source_label", "is_synthetic"],
        ).rename(columns={"source_label": "carbon_source", "is_synthetic": "carbon_is_synthetic"})
        for power_name, energy_name in (
            ("power_draw_kw", "modeled_energy_kwh"),
            ("it_load_kw", "modeled_it_energy_kwh"),
            ("cooling_power_kw", "modeled_cooling_energy_kwh"),
        ):
            joined[energy_name] = joined[power_name] * self.HOURS_PER_DAILY_OBSERVATION
        joined["modeled_energy_cost_usd"] = joined["modeled_energy_kwh"] * joined["price_per_kwh"]
        joined["modeled_it_cost_usd"] = joined["modeled_it_energy_kwh"] * joined["price_per_kwh"]
        joined["modeled_cooling_cost_usd"] = joined["modeled_cooling_energy_kwh"] * joined["price_per_kwh"]
        joined["modeled_carbon_tonnes"] = (
            joined["modeled_energy_kwh"] * joined["grams_co2e_per_kwh"] / self.GRAMS_PER_TONNE
        )
        joined["modeled_it_carbon_tonnes"] = (
            joined["modeled_it_energy_kwh"] * joined["grams_co2e_per_kwh"] / self.GRAMS_PER_TONNE
        )
        joined["modeled_cooling_carbon_tonnes"] = (
            joined["modeled_cooling_energy_kwh"] * joined["grams_co2e_per_kwh"] / self.GRAMS_PER_TONNE
        )
        joined["year"] = joined["timestamp"].dt.year
        joined["month"] = joined["timestamp"].dt.to_period("M").astype(str)
        return joined

    def summarize(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        facility_ids: list[str] | tuple[str, ...] | None = None,
    ) -> PortfolioSummary:
        daily = self.daily_model(start_date, end_date, facility_ids)
        if daily.empty:
            return PortfolioSummary(daily, {}, (), self._caveats())
        numeric = [
            "modeled_energy_kwh", "modeled_it_energy_kwh", "modeled_cooling_energy_kwh",
            "modeled_energy_cost_usd", "modeled_it_cost_usd", "modeled_cooling_cost_usd",
            "modeled_carbon_tonnes", "modeled_it_carbon_tonnes", "modeled_cooling_carbon_tonnes",
        ]
        grouped = daily.groupby(["facility_id", "facility_name"], as_index=False).agg(
            **{name: (name, "sum") for name in numeric},
            average_pue=("pue", "mean"),
            price_per_kwh=("price_per_kwh", "mean"),
            grams_co2e_per_kwh=("grams_co2e_per_kwh", "mean"),
            observation_days=("timestamp", "nunique"),
        )
        grouped["cooling_cost_share_pct"] = 100 * grouped["modeled_cooling_cost_usd"] / grouped["modeled_energy_cost_usd"]
        grouped["cost_per_it_kwh"] = grouped["modeled_energy_cost_usd"] / grouped["modeled_it_energy_kwh"]
        server_counts, incident_rates = self._facility_denominators(start_date, end_date)
        grouped["server_count"] = grouped["facility_id"].map(server_counts).fillna(0).astype(int)
        grouped["incident_rate_per_100_servers"] = grouped["facility_id"].map(incident_rates).fillna(0.0)
        grouped["cost_per_server_usd"] = np.where(
            grouped["server_count"] > 0,
            grouped["modeled_energy_cost_usd"] / grouped["server_count"], np.nan,
        )
        grouped["efficiency_opportunity_score"] = self._opportunity_score(grouped)
        totals = {name: float(grouped[name].sum()) for name in numeric}
        assumptions = tuple(
            daily[[
                "facility_id", "price_per_kwh", "currency", "pricing_basis", "price_source", "price_is_synthetic",
                "grams_co2e_per_kwh", "methodology", "carbon_source", "carbon_is_synthetic",
            ]].drop_duplicates().sort_values("facility_id").to_dict("records")
        )
        return PortfolioSummary(grouped, totals, assumptions, self._caveats())

    def _facility_denominators(
        self, start_date: str | None, end_date: str | None
    ) -> tuple[dict[str, int], dict[str, float]]:
        with connect_read_only(self.database_path) as connection:
            servers = {row[0]: int(row[1]) for row in connection.execute(
                "SELECT facility_id, COUNT(*) FROM servers GROUP BY facility_id"
            )}
            sql = "SELECT facility_id, COUNT(*) FROM uptime_incidents WHERE 1=1"
            params: list[object] = []
            if start_date:
                sql += " AND date(start_time)>=date(?)"
                params.append(start_date)
            if end_date:
                sql += " AND date(start_time)<=date(?)"
                params.append(end_date)
            sql += " GROUP BY facility_id"
            incident_counts = {row[0]: int(row[1]) for row in connection.execute(sql, params)}
        rates = {
            facility: 100.0 * incident_counts.get(facility, 0) / count
            for facility, count in servers.items() if count > 0
        }
        return servers, rates

    def _opportunity_score(self, frame: pd.DataFrame) -> pd.Series:
        components = {
            "pue": frame["average_pue"],
            "cooling_cost_per_it_kwh": frame["modeled_cooling_cost_usd"] / frame["modeled_it_energy_kwh"],
            "carbon_intensity": frame["grams_co2e_per_kwh"],
            "incident_rate": frame["incident_rate_per_100_servers"],
        }
        score = pd.Series(0.0, index=frame.index)
        for name, values in components.items():
            span = float(values.max() - values.min())
            normalized = (values - values.min()) / span if span > 0 else pd.Series(0.0, index=frame.index)
            score += self.weights[name] * normalized
        return (100 * score).round(2)

    def forecast(self, target_year: int) -> SustainabilityForecast:
        daily = self.daily_model()
        latest_year = int(daily["year"].max())
        if target_year <= latest_year:
            raise ValueError(f"Forecast year must be after {latest_year}")
        annual = daily.groupby(["facility_id", "facility_name", "year"], as_index=False).agg(
            modeled_energy_kwh=("modeled_energy_kwh", "sum"),
            modeled_it_energy_kwh=("modeled_it_energy_kwh", "sum"),
            modeled_cooling_energy_kwh=("modeled_cooling_energy_kwh", "sum"),
            average_pue=("pue", "mean"),
            base_price_per_kwh=("price_per_kwh", "mean"),
            base_carbon_intensity=("grams_co2e_per_kwh", "mean"),
            price_escalation_pct=("annual_escalation_pct", "mean"),
            carbon_change_pct=("annual_change_pct", "mean"),
        )
        output: list[dict[str, object]] = []
        for (facility_id, facility_name), rows in annual.groupby(["facility_id", "facility_name"]):
            years = rows["year"].to_numpy(dtype=float)
            record: dict[str, object] = {"facility_id": facility_id, "facility_name": facility_name, "target_year": target_year}
            for name in ("modeled_energy_kwh", "modeled_it_energy_kwh", "modeled_cooling_energy_kwh", "average_pue"):
                coefficients = np.polyfit(years, rows[name].to_numpy(dtype=float), 1)
                record[name] = max(0.0, float(np.polyval(coefficients, target_year)))
            latest = rows.sort_values("year").iloc[-1]
            years_ahead = target_year - latest_year
            price = float(latest["base_price_per_kwh"]) * (1 + float(latest["price_escalation_pct"]) / 100) ** years_ahead
            intensity = max(0.0, float(latest["base_carbon_intensity"]) * (1 + float(latest["carbon_change_pct"]) / 100) ** years_ahead)
            record.update({
                "projected_price_per_kwh": price,
                "projected_carbon_intensity_g_per_kwh": intensity,
                "projected_energy_cost_usd": float(record["modeled_energy_kwh"]) * price,
                "projected_cooling_cost_usd": float(record["modeled_cooling_energy_kwh"]) * price,
                "projected_carbon_tonnes": float(record["modeled_energy_kwh"]) * intensity / self.GRAMS_PER_TONNE,
                "is_projection": True,
                "assumptions_are_synthetic": True,
            })
            output.append(record)
        return SustainabilityForecast(
            target_year, pd.DataFrame(output).sort_values("facility_id").reset_index(drop=True),
            "Facility-level ordinary least-squares trend over annual 2015-2025 modeled energy; configured compound factor changes thereafter.",
            f"2015-{latest_year}", self._caveats(),
        )

    def efficiency_scenario(
        self,
        pue_reduction_pct: float,
        *,
        year: int = 2025,
        facility_ids: list[str] | tuple[str, ...] | None = None,
    ) -> pd.DataFrame:
        if not 0 <= pue_reduction_pct <= 50:
            raise ValueError("PUE reduction must be between 0% and 50%")
        daily = self.daily_model(f"{year}-01-01", f"{year}-12-31", facility_ids)
        if daily.empty:
            return daily
        reduction = pue_reduction_pct / 100.0
        baseline_cooling = daily["modeled_cooling_energy_kwh"]
        scenario_cooling = baseline_cooling * (1 - reduction)
        saved_kwh = baseline_cooling - scenario_cooling
        daily["scenario_pue"] = 1 + (daily["pue"] - 1) * (1 - reduction)
        daily["energy_savings_kwh"] = saved_kwh
        daily["cost_savings_usd"] = saved_kwh * daily["price_per_kwh"]
        daily["avoided_carbon_tonnes"] = saved_kwh * daily["grams_co2e_per_kwh"] / self.GRAMS_PER_TONNE
        return daily.groupby(["facility_id", "facility_name"], as_index=False).agg(
            baseline_pue=("pue", "mean"), scenario_pue=("scenario_pue", "mean"),
            energy_savings_kwh=("energy_savings_kwh", "sum"),
            cost_savings_usd=("cost_savings_usd", "sum"),
            avoided_carbon_tonnes=("avoided_carbon_tonnes", "sum"),
        )

    @staticmethod
    def _caveats() -> tuple[str, ...]:
        return (
            "Daily power rows are modeled as average kW sustained for 24 hours; no meter interval is implied.",
            "Prices and carbon intensities are synthetic portfolio-demo assumptions, not invoices or audited emissions.",
            "Forecasts extend historical linear trends and configured factor changes; they are estimates, not guarantees.",
        )

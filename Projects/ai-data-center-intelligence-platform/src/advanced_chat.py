"""Natural-language adapters for live, sustainability, and impact analytics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.conversation_context import ConversationContext
from src.database import connect_read_only
from src.impact.engine import ImpactAnalysisEngine
from src.investigation.service import MultiAgentInvestigationService
from src.realtime.configuration import RealtimeConfig
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService
from src.sustainability.engine import CostCarbonEngine


@dataclass(frozen=True)
class AdvancedAnswer:
    status: str
    answer: str
    frame: pd.DataFrame | None
    chart: dict[str, object] | None
    evidence: list[dict[str, object]]
    sources: list[str]
    validation_status: str
    execution_path: str
    confidence: str | None = None
    context_updates: dict[str, object] | None = None


class AdvancedAnalyticsChatService:
    """Turn flexible user wording into deterministic analytical operations."""

    METRIC_ALIASES = {
        "pue": "pue", "cooling": "cooling_power_kw", "cooling power": "cooling_power_kw",
        "power": "power_draw_kw", "energy": "power_draw_kw", "latency": "latency_ms",
        "packet loss": "packet_loss_pct", "availability": "network_availability_pct",
        "network availability": "network_availability_pct", "it load": "it_load_kw",
    }

    def __init__(self, project_root: Path, database_path: Path) -> None:
        self.project_root = project_root
        self.database_path = database_path
        self.sustainability = CostCarbonEngine(
            database_path,
            project_root / "data/assumptions/energy_prices.csv",
            project_root / "data/assumptions/carbon_intensity.csv",
            project_root / "analytics/efficiency_opportunity_weights.yaml",
        )
        self.impact = ImpactAnalysisEngine(database_path, self.sustainability)
        self.realtime_store: RealtimeStore | None = None
        self.streaming: StreamingAnalyticsService | None = None
        realtime_path = project_root / "database/realtime.db"
        if realtime_path.exists():
            self.realtime_store = RealtimeStore(
                realtime_path, database_path, project_root / "database/realtime_schema.sql"
            )
            config = RealtimeConfig.from_yaml(project_root / "config/realtime.yaml")
            self.streaming = StreamingAnalyticsService(
                self.realtime_store, config, project_root / "analytics/live_health_weights.yaml"
            )

    def answer(
        self, question: str, mode: str, context: ConversationContext
    ) -> AdvancedAnswer:
        handlers = {
            "COST_ANALYSIS": self._cost,
            "CARBON_ANALYSIS": self._carbon,
            "EFFICIENCY_SCENARIO": self._efficiency,
            "CORRELATION_ANALYSIS": self._correlation,
            "CAUSAL_ANALYSIS": self._causal,
            "INTERVENTION_ANALYSIS": self._intervention,
            "IMPACT_ANALYSIS": self._impact,
            "REALTIME_STATUS": self._realtime,
            "REALTIME_METRIC": self._realtime,
            "REALTIME_ANOMALY": self._realtime,
            "REALTIME_INCIDENT": self._realtime,
            "MULTI_AGENT_INVESTIGATION": self._multi_agent,
        }
        return handlers[mode](question, context, mode)

    def _facility_ids(self, context: ConversationContext) -> list[str]:
        if not context.facilities:
            return []
        with connect_read_only(self.database_path) as connection:
            placeholders = ",".join("?" for _ in context.facilities)
            return [row[0] for row in connection.execute(
                f"SELECT facility_id FROM facilities WHERE facility_name IN ({placeholders}) ORDER BY facility_id",
                context.facilities,
            )]

    @staticmethod
    def _years(question: str) -> list[int]:
        return sorted({int(value) for value in re.findall(r"\b20\d{2}\b", question)})

    def _cost(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del mode
        years = self._years(question)
        facilities = self._facility_ids(context)
        latest = 2025
        if years and max(years) > latest:
            result = self.sustainability.forecast(max(years))
            frame = result.frame
            if facilities:
                frame = frame[frame["facility_id"].isin(facilities)]
            answer = (
                f"The modeled {result.target_year} portfolio energy cost is ${frame['projected_energy_cost_usd'].sum():,.0f}; "
                f"the cooling portion is ${frame['projected_cooling_cost_usd'].sum():,.0f}. "
                f"Projected facility energy prices range from ${frame['projected_price_per_kwh'].min():.3f} to "
                f"${frame['projected_price_per_kwh'].max():.3f} per kWh. These are synthetic assumptions and trend estimates, not invoices or guarantees."
            )
            return AdvancedAnswer(
                "cost_forecast", answer, frame,
                {"kind": "bar", "x": "facility_name", "y": "projected_energy_cost_usd"},
                [{"method": result.method, "training_period": result.training_period, "caveats": result.caveats}],
                ["power_metrics", "energy_prices.csv"], "governed_projection", "cost_carbon_forecast",
                context_updates={"chart_state": {"kind": "bar", "metric": "projected_energy_cost_usd"}},
            )
        selected_years = years or [latest]
        frames = []
        for year in selected_years:
            summary = self.sustainability.summarize(
                f"{year}-01-01", f"{year}-12-31", facilities or None
            )
            part = summary.frame.copy()
            if not part.empty:
                part.insert(2, "year", year)
                frames.append(part)
        if not frames:
            return self._clarification("No modeled cost rows matched that scope.")
        frame = pd.concat(frames, ignore_index=True)
        by_year = frame.groupby("year", as_index=False)[["modeled_energy_cost_usd", "modeled_cooling_cost_usd"]].sum()
        lines = "; ".join(
            f"{int(row.year)}: ${row.modeled_energy_cost_usd:,.0f} total (${row.modeled_cooling_cost_usd:,.0f} cooling)"
            for row in by_year.itertuples()
        )
        direction = ""
        if len(by_year) > 1:
            direction = " The modeled cost increased." if by_year.iloc[-1]["modeled_energy_cost_usd"] > by_year.iloc[0]["modeled_energy_cost_usd"] else " The modeled cost decreased."
        return AdvancedAnswer(
            "cost_analysis", f"Modeled energy cost — {lines}.{direction} Values use synthetic USD/kWh assumptions, not actual bills.",
            frame, {"kind": "line", "x": "year", "y": "modeled_energy_cost_usd"},
            [{"assumptions": "date-effective synthetic energy prices", "years": selected_years}],
            ["power_metrics", "energy_prices.csv"], "governed_cost_formula", "cost_analysis",
            context_updates={"chart_state": {"kind": "line", "metric": "modeled_energy_cost_usd"}},
        )

    def _carbon(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del mode
        years = self._years(question)
        facilities = self._facility_ids(context)
        if years and max(years) > 2025:
            result = self.sustainability.forecast(max(years))
            frame = result.frame
            if facilities:
                frame = frame[frame["facility_id"].isin(facilities)]
            answer = (
                f"The modeled {result.target_year} emissions estimate is {frame['projected_carbon_tonnes'].sum():,.2f} tonnes CO2e. "
                "It uses synthetic location-based factors and is not an audited inventory or guarantee."
            )
            return AdvancedAnswer(
                "carbon_forecast", answer, frame,
                {"kind": "bar", "x": "facility_name", "y": "projected_carbon_tonnes"},
                [{"method": result.method, "training_period": result.training_period, "caveats": result.caveats}],
                ["power_metrics", "carbon_intensity.csv"], "governed_projection", "cost_carbon_forecast",
                context_updates={"chart_state": {"kind": "bar", "metric": "projected_carbon_tonnes"}},
            )
        year = max(years) if years else 2025
        result = self.sustainability.summarize(f"{year}-01-01", f"{year}-12-31", facilities or None)
        frame = result.frame
        return AdvancedAnswer(
            "carbon_analysis",
            f"Modeled {year} emissions are {frame['modeled_carbon_tonnes'].sum():,.2f} tonnes CO2e, including "
            f"{frame['modeled_cooling_carbon_tonnes'].sum():,.2f} tonnes from cooling. Synthetic factors are used; this is not an audited inventory.",
            frame, {"kind": "bar", "x": "facility_name", "y": "modeled_carbon_tonnes"},
            [{"assumptions": list(result.assumptions), "caveats": result.caveats}],
            ["power_metrics", "carbon_intensity.csv"], "governed_carbon_formula", "carbon_analysis",
            context_updates={"chart_state": {"kind": "bar", "metric": "modeled_carbon_tonnes"}},
        )

    def _efficiency(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del mode
        percent = re.search(r"(\d+(?:\.\d+)?)\s*%", question)
        if not percent:
            return self._clarification("What PUE or cooling-efficiency improvement percentage should I model?")
        value = float(percent.group(1))
        year = max(self._years(question) or [2025])
        frame = self.sustainability.efficiency_scenario(value, year=year, facility_ids=self._facility_ids(context) or None)
        return AdvancedAnswer(
            "efficiency_scenario",
            f"A {value:g}% cooling-efficiency improvement in {year} models {frame['energy_savings_kwh'].sum():,.0f} kWh, "
            f"${frame['cost_savings_usd'].sum():,.0f}, and {frame['avoided_carbon_tonnes'].sum():,.2f} tonnes CO2e avoided. "
            "This is deterministic scenario arithmetic using synthetic factors, not a guaranteed outcome.",
            frame, {"kind": "bar", "x": "facility_name", "y": "cost_savings_usd"},
            [{"user_assumption_pct": value, "year": year}],
            ["power_metrics", "energy_prices.csv", "carbon_intensity.csv"],
            "governed_scenario", "efficiency_scenario",
            context_updates={"chart_state": {"kind": "bar", "metric": "cost_savings_usd"}},
        )

    def _correlation(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del mode
        metrics = self._detect_impact_metrics(question)
        if len(metrics) < 2:
            return self._clarification("Which two metrics should I compare, for example PUE and cooling power?")
        facility_ids = self._facility_ids(context)
        if "lead" in question.lower() or "lag" in question.lower():
            if not facility_ids:
                return self._clarification("Which facility should the lead-lag analysis use?")
            frame = self.impact.lead_lag(metrics[0], metrics[1], facility_id=facility_ids[0])
            best = frame.loc[frame["coefficient"].abs().idxmax()]
            answer = (
                f"The strongest tested temporal association is at lag {int(best['lag_days'])} days "
                f"(coefficient {float(best['coefficient']):.3f}, n={int(best['sample_size'])}). "
                "Positive lag means the first metric appears earlier. This does not establish causation."
            )
            return AdvancedAnswer(
                "lead_lag_analysis", answer, frame, {"kind": "line", "x": "lag_days", "y": "coefficient"},
                [{"leading_metric": metrics[0], "outcome_metric": metrics[1]}],
                [self.impact.METRIC_COLUMNS[metrics[0]][0], self.impact.METRIC_COLUMNS[metrics[1]][0]],
                "temporal_association", "lead_lag_analysis",
                context_updates={"chart_state": {"kind": "line", "metric": "coefficient"}},
            )
        result = self.impact.correlation(
            metrics[0], metrics[1], facility_id=facility_ids[0] if facility_ids else None,
            start_date=context.start_date, end_date=context.end_date,
        )
        interval = result.confidence_interval_95
        interval_text = "unavailable" if interval is None else f"{interval[0]:.3f} to {interval[1]:.3f}"
        return AdvancedAnswer(
            "correlation_analysis",
            f"{metrics[0]} and {metrics[1]} have coefficient {result.coefficient:.3f} (95% interval {interval_text}, n={result.sample_size}). " + result.interpretation,
            result.chart_data, {"kind": "scatter", "x": metrics[0], "y": metrics[1]},
            [{"window": result.window, "scope": result.scope, "sample_size": result.sample_size}],
            [self.impact.METRIC_COLUMNS[metrics[0]][0], self.impact.METRIC_COLUMNS[metrics[1]][0]],
            "statistical_association", "correlation_analysis",
            context_updates={"chart_state": {"kind": "scatter", "x": metrics[0], "y": metrics[1]}},
        )

    def _causal(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del mode
        if not context.intervention_date:
            return self._clarification(
                "I can test causal evidence only around a defined intervention. What change and intervention date should I use?"
            )
        return self._intervention(question, context, "INTERVENTION_ANALYSIS")

    def _intervention(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del mode
        metrics = self._detect_impact_metrics(question)
        facilities = self._facility_ids(context)
        if not context.intervention_date:
            return self._clarification("What was the intervention date?")
        if not metrics:
            return self._clarification("Which outcome metric should I evaluate after the intervention?")
        if not facilities:
            return self._clarification("Which facility received the intervention?")
        comparison = facilities[1] if len(facilities) > 1 else None
        result = self.impact.intervention(
            metrics[0], context.intervention_date,
            treated_facility_id=facilities[0], comparison_facility_id=comparison,
        )
        return AdvancedAnswer(
            "intervention_analysis",
            f"Using {result.method}, the estimated {metrics[0]} change is {result.estimated_change:,.4f} {result.unit} "
            f"across {result.sample_size} rows. {result.interpretation}",
            result.chart_data, {"kind": "line", "x": "date", "y": "value", "color": "facility_id"},
            [{"assumptions_met": result.assumptions_met, "assumptions_failed": result.assumptions_failed, "evidence_score": result.evidence_score}],
            [self.impact.METRIC_COLUMNS[metrics[0]][0]], "guarded_quasi_experimental", "intervention_analysis",
            confidence=str(result.evidence_score["overall_qualitative"]),
            context_updates={"causal_method": result.method, "chart_state": {"kind": "line", "metric": metrics[0]}},
        )

    def _impact(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del question, mode
        if not context.incident_id:
            return self._clarification("Which incident ID should I evaluate?")
        result = self.impact.incident_impact(context.incident_id)
        frame = pd.DataFrame(result["metrics"])
        return AdvancedAnswer(
            "impact_analysis",
            f"{context.incident_id} lasted {result['duration_minutes']} minutes. "
            f"I compared {len(frame)} metrics before, during, and after the event. {result['caveat']}",
            frame, {"kind": "bar", "x": "metric", "y": "during_change_pct"},
            [result], ["uptime_incidents", "power_metrics", "network_metrics"],
            "descriptive_incident_impact", "incident_impact",
            context_updates={"chart_state": {"kind": "bar", "metric": "during_change_pct"}},
        )

    def _session_id(self, context: ConversationContext) -> str | None:
        if context.simulation_session_id:
            return context.simulation_session_id
        return None if self.realtime_store is None else self.realtime_store.latest_session_id()

    def _realtime(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        session_id = self._session_id(context)
        if not session_id or self.streaming is None:
            return self._clarification("No real-time simulation session is available. Start a scenario in the Simulation Lab first.")
        facility_ids = self._facility_ids(context)
        status = self.streaming.current_status(session_id, facility_ids[0] if facility_ids else None)
        if mode == "REALTIME_ANOMALY":
            frame = pd.DataFrame(status.active_anomalies)
            answer = f"Session {session_id} has {len(frame)} active online anomalies."
            sources = ["realtime_anomalies"]
        elif mode == "REALTIME_INCIDENT":
            with self.realtime_store.read_connection() as connection:
                frame = pd.read_sql_query(
                    "SELECT * FROM realtime_incident_events WHERE simulation_session_id=? ORDER BY event_timestamp",
                    connection, params=[session_id],
                )
            answer = f"Session {session_id} has {frame['incident_id'].nunique() if not frame.empty else 0} observed incidents and {len(frame)} lifecycle events."
            sources = ["realtime_incident_events"]
        elif mode == "REALTIME_METRIC":
            frame = pd.DataFrame(status.metrics)
            requested = self._detect_live_metric(question)
            if requested and not frame.empty:
                frame = frame[frame["metric_name"] == requested]
            answer = f"Session {session_id} has {len(frame)} current metric values" + (f" for {requested}." if requested else ".")
            sources = ["realtime_metric_state"]
        else:
            frame = pd.DataFrame(status.facility_health)
            answer = (
                f"Session {session_id} is current={status.state_is_current}, with {len(status.active_anomalies)} active anomalies, "
                f"{len(status.active_alerts)} active alerts, and {len(frame)} facility health scores."
            )
            sources = ["realtime_metric_state", "realtime_facility_health", "realtime_anomalies", "realtime_alert_events"]
        return AdvancedAnswer(
            mode.lower(), answer, frame, None,
            [{"session_id": session_id, "event_version": status.event_version, "state_version": status.state_version}],
            sources, "live_state_current" if status.state_is_current else "live_state_lagging", "realtime",
            context_updates={"simulation_session_id": session_id, "data_mode": "live"},
        )

    def _multi_agent(self, question: str, context: ConversationContext, mode: str) -> AdvancedAnswer:
        del question, mode
        session_id = self._session_id(context)
        if not session_id or self.realtime_store is None:
            return self._clarification("No simulation session is available for specialist investigation.")
        facilities = self._facility_ids(context)
        report = MultiAgentInvestigationService(
            self.realtime_store, self.database_path
        ).investigate(session_id, facilities[0] if facilities else None)
        frame = pd.DataFrame([item.to_dict() for item in report.evidence_timeline])
        return AdvancedAnswer(
            "multi_agent_investigation",
            f"{report.incident_summary} Leading finding: {report.likely_contributor} "
            f"Confidence: {report.confidence_label}. {report.uncertainty}",
            frame, None, [report.to_dict()],
            sorted({item.source for item in report.evidence_timeline}),
            "evidence_verified" if report.verified else "insufficient_evidence",
            "multi_agent_investigation", report.confidence_label,
            {"simulation_session_id": session_id, "data_mode": "live"},
        )

    def _detect_impact_metrics(self, question: str) -> list[str]:
        lower = question.lower()
        found: list[tuple[int, str]] = []
        for phrase, metric in sorted(self.METRIC_ALIASES.items(), key=lambda item: -len(item[0])):
            match = re.search(rf"\b{re.escape(phrase)}\b", lower)
            if match and metric not in [item[1] for item in found]:
                found.append((match.start(), metric))
        return [metric for _, metric in sorted(found)]

    @staticmethod
    def _detect_live_metric(question: str) -> str | None:
        lower = question.lower()
        aliases = {
            "pue": "pue", "latency": "latency_ms", "packet loss": "packet_loss_pct",
            "temperature": "temperature_c", "cpu": "cpu_utilization_pct",
            "memory": "memory_utilization_pct", "disk": "disk_utilization_pct",
            "cooling": "cooling_power_kw", "power": "power_draw_kw",
        }
        return next((metric for phrase, metric in aliases.items() if phrase in lower), None)

    @staticmethod
    def _clarification(message: str) -> AdvancedAnswer:
        return AdvancedAnswer(
            "clarification", message, None, None, [], [], "needs_input", "clarification"
        )

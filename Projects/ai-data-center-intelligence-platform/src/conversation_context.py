"""Compact structured conversation state for operational follow-ups."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from datetime import date

from src.forecasting import detect_metric
from src.question_analyzer import FACILITIES


@dataclass(frozen=True)
class ConversationContext:
    facilities: tuple[str, ...] = ()
    server_id: str | None = None
    incident_id: str | None = None
    related_incident_id: str | None = None
    metric_key: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    analysis_mode: str | None = None
    simulation_session_id: str | None = None
    data_mode: str | None = None
    cost_scenario: str | None = None
    carbon_scenario: str | None = None
    intervention_date: str | None = None
    comparison_facility: str | None = None
    causal_method: str | None = None
    chart_state: dict[str, object] | None = None

    @classmethod
    def from_value(cls, value: "ConversationContext | dict | None") -> "ConversationContext":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        payload = {key: item for key, item in value.items() if key in allowed}
        if "facilities" in payload:
            payload["facilities"] = tuple(payload["facilities"] or ())
        return cls(**payload)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        # Keep the long-standing compact shape unchanged until an advanced
        # feature actually needs one of the new context fields.
        optional = {
            "simulation_session_id", "data_mode", "cost_scenario",
            "carbon_scenario", "intervention_date", "comparison_facility",
            "causal_method", "chart_state",
        }
        return {
            key: value for key, value in payload.items()
            if key not in optional or value not in (None, {}, ())
        }


class ContextResolver:
    _MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }

    @classmethod
    def _natural_dates(cls, question: str) -> list[str]:
        month_names = "|".join(cls._MONTHS)
        patterns = (
            rf"\b({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(20\d{{2}})\b",
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})(?:,)?\s+(20\d{{2}})\b",
        )
        values: list[str] = []
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, question, re.IGNORECASE):
                if index == 0:
                    month_name, day_value, year_value = match.groups()
                else:
                    day_value, month_name, year_value = match.groups()
                try:
                    values.append(
                        date(
                            int(year_value), cls._MONTHS[month_name.lower()], int(day_value)
                        ).isoformat()
                    )
                except ValueError:
                    continue
        return values

    def resolve(
        self,
        question: str,
        previous: ConversationContext | dict | None = None,
    ) -> ConversationContext:
        previous_context = ConversationContext.from_value(previous)
        lower = question.lower()
        explicit_facilities = tuple(dict.fromkeys(
            canonical for alias, canonical in FACILITIES.items() if alias in lower
        ))
        server_match = re.search(r"\bsrv-\d+\b", lower, re.IGNORECASE)
        incident_match = re.search(r"\binc-\d+\b", lower, re.IGNORECASE)
        session_match = re.search(r"\bsim-[a-z0-9-]+\b", lower, re.IGNORECASE)
        metric = detect_metric(question)
        dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", question)
        dates.extend(self._natural_dates(question))
        years = re.findall(r"\b(20\d{2})\b", question)
        start_date = end_date = None
        if dates:
            start_date, end_date = min(dates), max(dates)
        elif years:
            start_date, end_date = f"{min(years)}-01-01", f"{max(years)}-12-31"
        context = previous_context
        if explicit_facilities:
            changed = explicit_facilities != previous_context.facilities
            context = replace(
                context,
                facilities=explicit_facilities,
                incident_id=None if changed and not incident_match else context.incident_id,
                related_incident_id=(
                    None if changed and not incident_match else context.related_incident_id
                ),
                server_id=None if changed and not server_match else context.server_id,
            )
        if server_match:
            context = replace(context, server_id=server_match.group(0).upper())
        if incident_match:
            context = replace(
                context,
                incident_id=incident_match.group(0).upper(),
                related_incident_id=None,
            )
        if session_match:
            context = replace(context, simulation_session_id=session_match.group(0).upper())
        if re.search(r"\b(real[- ]?time|live|right now|current telemetry)\b", lower):
            context = replace(context, data_mode="live")
        elif re.search(r"\bhistorical(?:ly)?\b|\bpast data\b", lower):
            context = replace(context, data_mode="historical")
        if metric:
            context = replace(context, metric_key=metric.key)
        if start_date:
            context = replace(context, start_date=start_date, end_date=end_date)
            if re.search(r"\b(intervention|upgrade|change|maintenance|deployment)\b", lower):
                context = replace(context, intervention_date=start_date)
        if re.search(r"\b(cost|price|spend|savings?)\b", lower):
            context = replace(context, cost_scenario="active")
        if re.search(r"\b(carbon|co2e|emissions?)\b", lower):
            context = replace(context, carbon_scenario="active")
        if re.search(r"\bdifference[- ]in[- ]differences?\b|\bdid\b", lower):
            context = replace(context, causal_method="difference_in_differences")
        elif re.search(r"\binterrupted time series\b|\bits\b", lower):
            context = replace(context, causal_method="interrupted_time_series")
        return context

    @staticmethod
    def with_mode(context: ConversationContext, mode: str) -> ConversationContext:
        return replace(context, analysis_mode=mode)

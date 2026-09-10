from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.forecasting import detect_metric, detect_metrics


@dataclass(frozen=True)
class RouteDecision:
    category: str
    metric_key: str | None = None
    facilities: tuple[str, ...] = field(default_factory=tuple)
    years: tuple[int, ...] = field(default_factory=tuple)
    ranking_direction: str | None = None
    top_one: bool = False
    definition_answer: str | None = None
    group_by_facility: bool = False


class FastQueryRouter:
    """Classify deterministic analytics before the local model is considered."""

    def __init__(self, glossary_path: Path | str) -> None:
        terms = yaml.safe_load(Path(glossary_path).read_text(encoding="utf-8"))["terms"]
        aliases = []
        for term, definition in terms.items():
            for alias in {term, *definition.get("synonyms", [])}:
                aliases.append((str(alias).lower(), term, definition))
        self.aliases = sorted(aliases, key=lambda item: len(item[0]), reverse=True)

    def definition(self, question: str) -> RouteDecision | None:
        lower = question.lower().strip()
        if re.search(r"\b20\d{2}\b", lower):
            return None
        if not re.search(r"^(what (?:is|are|does)|define|meaning of|explain the term)", lower):
            return None
        if re.search(r"\b(average|total|highest|lowest|count|compare|show|list)\b", lower):
            return None
        for alias, term, definition in self.aliases:
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", lower):
                canonical = definition.get("canonical_term") or term.replace("_", " ").title()
                answer = f"**{canonical}:** {definition['definition']}"
                if definition.get("caveat"):
                    answer += f" {definition['caveat']}"
                if definition.get("source"):
                    answer += f" Source: `{definition['source']}`."
                return RouteDecision("DEFINITION", definition_answer=answer)
        return None

    def route(self, question: str, analysis, latest_complete_year: int) -> RouteDecision:
        definition = self.definition(question)
        if definition is not None:
            return definition
        metrics = detect_metrics(question)
        metric = detect_metric(question)
        if metric is None or len(metrics) > 1:
            return RouteDecision("AI")
        years = tuple(year for year in analysis.years if year <= latest_complete_year)
        facilities = tuple(analysis.facilities)
        lower = question.lower()
        if years and re.search(r"\b(price|expense|spend|bill)\b", lower) and "cooling" not in lower:
            return RouteDecision("AI")
        if re.search(
            r"\bsrv-\d+\b|\bserver type\b|\broot cause\b|\bmonthly\b|\bmonth\b|"
            r"\bquarter(?:ly)?\b|\bdaily\b|\bday\b|\brack\b|\bseverity\b|"
            r"\bindividual server\b|\bper server\b|\bby server\b|\b20\d{2}-\d{2}-\d{2}\b",
            lower,
        ):
            return RouteDecision("AI")
        if re.search(r"\b(increase|increse|decrease|decrese|rise|fall|grow|decline|up|down)\b", lower):
            return RouteDecision("AI")
        ranking = re.search(
            r"\b(highest|largest|greatest|most|lowest|smallest|least|best|worst|rank|ranking)\b",
            lower,
        )
        if ranking:
            token = ranking.group(1)
            lower_is_better = metric.key in {
                "average_pue", "cooling_cost", "latency_ms", "packet_loss_pct",
                "downtime_minutes", "incident_count",
            }
            if token in {"lowest", "smallest", "least"}:
                direction = "ASC"
            elif token == "best":
                direction = "ASC" if lower_is_better else "DESC"
            elif token == "worst":
                direction = "DESC" if lower_is_better else "ASC"
            else:
                direction = "DESC"
            return RouteDecision(
                "RANKING", metric.key, facilities, years, direction, token != "rank" and token != "ranking"
            )
        if re.search(r"\b(compare|comparison|versus|vs\.?|between)\b", lower) and (
            len(facilities) >= 2 or len(years) >= 2
        ):
            return RouteDecision("COMPARISON", metric.key, facilities, years)
        if re.search(
            r"\b(trend|annual|yearly|by year|by facility (?:and|by) year|over time|from 20\d{2})\b",
            lower,
        ):
            year_range = re.search(r"\bfrom\s+(20\d{2})\s+(?:to|through|thru|-)\s*(20\d{2})\b", lower)
            if year_range:
                start_year, end_year = map(int, year_range.groups())
                years = tuple(range(min(start_year, end_year), max(start_year, end_year) + 1))
            group_by_facility = bool(re.search(r"\bby\s+facility\b|\bby\s+site\b", lower))
            return RouteDecision(
                "TREND", metric.key, facilities, years, group_by_facility=group_by_facility
            )
        if years or facilities or re.search(r"\b(how many|average|total|count)\b", lower):
            return RouteDecision("SIMPLE_KPI", metric.key, facilities, years)
        return RouteDecision("AI")

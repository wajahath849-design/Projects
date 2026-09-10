from __future__ import annotations

import re
from dataclasses import dataclass, field


FACILITIES = {
    "frankfurt": "Frankfurt Central", "dublin": "Dublin West", "ashburn": "Ashburn East",
    "portland": "Portland West", "singapore": "Singapore South", "sydney": "Sydney Pacific",
}
DOMAIN_TERMS = {
    "energy": {"pue", "power", "cooling", "energy", "cost", "price", "expense", "spend", "bill"},
    "server_performance": {"server", "cpu", "memory", "disk", "utilization"},
    "network": {"network", "latency", "packet", "throughput", "bandwidth"},
    "reliability": {"incident", "downtime", "outage", "availability", "root cause"},
}


@dataclass
class QuestionAnalysis:
    relevant: bool
    domains: list[str] = field(default_factory=list)
    facilities: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    ambiguous: bool = False
    clarification: str | None = None
    unsafe: bool = False
    relative_period: str | None = None


class QuestionAnalyzer:
    def __init__(self, available_modules: set[str], latest_year: int = 2025) -> None:
        self.available_modules = available_modules
        self.latest_year = latest_year

    def analyze(self, question: str) -> QuestionAnalysis:
        lower = question.lower().strip()
        unsafe = bool(re.search(r"\b(drop|delete|update|insert|alter|attach|pragma|vacuum)\b", lower))
        domains = [name for name, terms in DOMAIN_TERMS.items() if any(term in lower for term in terms)]
        facilities = [canonical for alias, canonical in FACILITIES.items() if alias in lower]
        years = sorted({int(year) for year in re.findall(r"\b(20\d{2})\b", lower)})
        ambiguous = bool(re.search(r"\b(best|worst|performing well|most improved)\b", lower)) and not any(
            term in lower for terms in DOMAIN_TERMS.values() for term in terms
        )
        relative = None
        if "last year" in lower:
            years.append(self.latest_year - 1)
            relative = "last year"
        elif "last month" in lower:
            relative = "2025-12"
        elif "last quarter" in lower:
            relative = "2025-Q4"
        unavailable = [domain for domain in domains if domain not in self.available_modules]
        clarification = None
        if ambiguous:
            clarification = "Which metric should define best: PUE, downtime, availability, incident rate, or cooling cost?"
        elif unavailable:
            clarification = f"The required module is unavailable: {', '.join(unavailable)}."
        relevant = bool(domains) and not unavailable
        return QuestionAnalysis(relevant, domains, facilities, sorted(set(years)), ambiguous, clarification, unsafe, relative)

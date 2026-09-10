"""Canonical investigation evidence with deterministic deduplication."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    evidence_type: str
    source: str
    timestamp: str
    facility_id: str
    server_id: str | None
    metric_or_event: str
    value: Any
    severity: str | None
    relevance: str
    agent: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deduplicate_evidence(records: Iterable[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
    """Keep one canonical copy of each database-backed evidence identifier."""
    unique: dict[str, EvidenceRecord] = {}
    for record in records:
        unique.setdefault(record.evidence_id, record)
    return tuple(sorted(unique.values(), key=lambda item: (item.timestamp, item.evidence_id)))

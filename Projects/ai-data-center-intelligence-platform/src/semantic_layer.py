from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    metadata: dict[str, str]


class SemanticLayer:
    """Build allow-listed RAG chunks. Evaluation paths are impossible inputs."""

    def __init__(self, project_root: Path | str) -> None:
        self.root = Path(project_root)
        self.allowed = [
            self.root / "analytics/canonical_data_contract.json",
            self.root / "analytics/metric_definitions.yaml",
            self.root / "analytics/business_glossary.yaml",
            self.root / "analytics/kpi_catalog.yaml",
            self.root / "analytics/forecast_definitions.yaml",
            self.root / "knowledge/incident_knowledge.yaml",
            self.root / "knowledge/runbooks.yaml",
            self.root / "knowledge/error_codes.yaml",
        ]

    def _validate_sources(self) -> None:
        root = self.root.resolve()
        for path in self.allowed:
            resolved = path.resolve()
            if root not in resolved.parents:
                raise RuntimeError(f"Knowledge source is outside the project root: {path}")
            relative_parts = {part.lower() for part in resolved.relative_to(root).parts}
            if "evaluation" in relative_parts:
                raise RuntimeError("Evaluation content cannot enter production knowledge")
            if not resolved.is_file():
                raise FileNotFoundError(f"Knowledge source is missing: {path}")

    def build_chunks(self) -> list[KnowledgeChunk]:
        self._validate_sources()
        contract = json.loads(self.allowed[0].read_text(encoding="utf-8"))
        metrics = yaml.safe_load(self.allowed[1].read_text(encoding="utf-8"))["metrics"]
        glossary = yaml.safe_load(self.allowed[2].read_text(encoding="utf-8"))["terms"]
        forecast_definitions = yaml.safe_load(self.allowed[4].read_text(encoding="utf-8"))
        incident_knowledge = yaml.safe_load(self.allowed[5].read_text(encoding="utf-8"))["incidents"]
        runbooks = yaml.safe_load(self.allowed[6].read_text(encoding="utf-8"))["runbooks"]
        error_codes = yaml.safe_load(self.allowed[7].read_text(encoding="utf-8"))["error_codes"]
        chunks = []
        for table, definition in contract["tables"].items():
            columns = ", ".join(
                f"{name} ({rule['type']}): {rule['description']}"
                for name, rule in definition["columns"].items()
            )
            relationships = "; ".join(
                f"{fk['columns']} references {fk['references_table']}.{fk['references_columns']}"
                for fk in definition["foreign_keys"]
            ) or "no foreign keys"
            chunks.append(KnowledgeChunk(
                f"schema:{table}",
                f"Table {table}. {definition['description']} Grain {definition['grain']}. Columns: {columns}. Relationships: {relationships}.",
                {"kind": "schema", "collection": "schema", "table": table, "source": "analytics/canonical_data_contract.json"},
            ))
        for metric, definition in metrics.items():
            chunks.append(KnowledgeChunk(
                f"metric:{metric}",
                f"Metric {metric}: {definition}",
                {"kind": "metric", "collection": "kpi_definitions", "metric": metric, "source": "analytics/metric_definitions.yaml"},
            ))
        for term, definition in glossary.items():
            chunks.append(KnowledgeChunk(
                f"glossary:{term}",
                f"Business term {term}: {definition}",
                {"kind": "glossary", "collection": "glossary", "term": term, "source": "analytics/business_glossary.yaml"},
            ))
        for metric, definition in forecast_definitions["supported_metrics"].items():
            chunks.append(KnowledgeChunk(
                f"forecast:{metric}",
                f"Forecast metric {metric}: {definition}. Method: {forecast_definitions['method']}",
                {"kind": "forecast_definition", "collection": "forecast_definitions", "metric": metric, "source": "analytics/forecast_definitions.yaml"},
            ))
        verified_examples = {
            "highest_pue": "Question pattern: highest average PUE by facility and year. Verified SQL pattern: join power_metrics to facilities, filter a half-open calendar-year range, group by facility, order AVG(pue) descending, and limit 1.",
            "downtime_per_server": "Question pattern: most downtime per server. Verified SQL pattern: query vw_facility_reliability, order downtime_minutes_per_server descending, and limit 1.",
            "cooling_cost_trend": "Question pattern: cooling cost over years. Verified SQL pattern: group SUM(cooling_cost) by substr(timestamp,1,4), filter with a half-open date range, and order by year.",
        }
        for name, text in verified_examples.items():
            chunks.append(KnowledgeChunk(
                f"sql_example:{name}", text,
                {"kind": "verified_sql_example", "collection": "sql_examples", "source": "src/semantic_layer.py"},
            ))
        for name, definition in incident_knowledge.items():
            chunks.append(KnowledgeChunk(
                f"incident_knowledge:{name}",
                " ".join([
                    f"Incident knowledge {name}: {definition['incident_type']}.",
                    f"Symptoms: {', '.join(definition['symptoms'])}.",
                    f"Affected components: {', '.join(definition['affected_components'])}.",
                    f"Common log codes: {', '.join(definition['common_log_codes'])}.",
                    f"Related metrics: {', '.join(definition['related_metrics'])}.",
                    f"Likely causes to investigate: {', '.join(definition['likely_causes'])}.",
                    f"Recommended checks: {'; '.join(definition['recommended_checks'])}.",
                    f"Historical resolution pattern: {definition['historical_resolution']}",
                    f"Limitation: {definition['limitation']}",
                ]),
                {
                    "kind": "incident_knowledge",
                    "collection": "incident_knowledge",
                    "incident_type": name,
                    "source": "knowledge/incident_knowledge.yaml",
                },
            ))
        for name, definition in runbooks.items():
            chunks.append(KnowledgeChunk(
                f"runbook:{name}",
                " ".join([
                    f"Runbook {definition['title']}.",
                    f"Applies to: {', '.join(definition['applies_to'])}.",
                    f"Safety: {definition['safety']}",
                    f"Steps: {'; '.join(definition['steps'])}.",
                ]),
                {
                    "kind": "runbook",
                    "collection": "runbooks",
                    "runbook": name,
                    "source": "knowledge/runbooks.yaml",
                },
            ))
        for code, definition in error_codes.items():
            chunks.append(KnowledgeChunk(
                f"error_code:{code}",
                f"Error code {code}. Component: {definition['component']}. Meaning: {definition['meaning']}. Recommended check: {definition['check']}",
                {
                    "kind": "error_code",
                    "collection": "error_codes",
                    "event_code": code,
                    "source": "knowledge/error_codes.yaml",
                },
            ))
        return chunks

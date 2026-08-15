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
        ]

    def build_chunks(self) -> list[KnowledgeChunk]:
        if any("evaluation" in path.parts for path in self.allowed):
            raise RuntimeError("Evaluation content cannot enter production knowledge")
        contract = json.loads(self.allowed[0].read_text(encoding="utf-8"))
        metrics = yaml.safe_load(self.allowed[1].read_text(encoding="utf-8"))["metrics"]
        glossary = yaml.safe_load(self.allowed[2].read_text(encoding="utf-8"))["terms"]
        forecast_definitions = yaml.safe_load(self.allowed[4].read_text(encoding="utf-8"))
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
                {"kind": "schema", "table": table, "source": "analytics/canonical_data_contract.json"},
            ))
        for metric, definition in metrics.items():
            chunks.append(KnowledgeChunk(
                f"metric:{metric}",
                f"Metric {metric}: {definition}",
                {"kind": "metric", "metric": metric, "source": "analytics/metric_definitions.yaml"},
            ))
        for term, definition in glossary.items():
            chunks.append(KnowledgeChunk(
                f"glossary:{term}",
                f"Business term {term}: {definition}",
                {"kind": "glossary", "term": term, "source": "analytics/business_glossary.yaml"},
            ))
        for metric, definition in forecast_definitions["supported_metrics"].items():
            chunks.append(KnowledgeChunk(
                f"forecast:{metric}",
                f"Forecast metric {metric}: {definition}. Method: {forecast_definitions['method']}",
                {"kind": "forecast_definition", "metric": metric, "source": "analytics/forecast_definitions.yaml"},
            ))
        verified_examples = {
            "highest_pue": "Question pattern: highest average PUE by facility and year. Verified SQL pattern: join power_metrics to facilities, filter a half-open calendar-year range, group by facility, order AVG(pue) descending, and limit 1.",
            "downtime_per_server": "Question pattern: most downtime per server. Verified SQL pattern: query vw_facility_reliability, order downtime_minutes_per_server descending, and limit 1.",
            "cooling_cost_trend": "Question pattern: cooling cost over years. Verified SQL pattern: group SUM(cooling_cost) by substr(timestamp,1,4), filter with a half-open date range, and order by year.",
        }
        for name, text in verified_examples.items():
            chunks.append(KnowledgeChunk(
                f"sql_example:{name}", text,
                {"kind": "verified_sql_example", "source": "src/semantic_layer.py"},
            ))
        return chunks

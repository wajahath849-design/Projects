from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.schema_mapper import SchemaMapper


@dataclass
class AdaptationResult:
    table: str
    frame: pd.DataFrame
    mapping: dict[str, str]
    generated_columns: list[str]
    warnings: list[str]


class DatasetAdapter:
    def __init__(self, contract_path: Path | str, aliases_path: Path | str) -> None:
        self.contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
        self.mapper = SchemaMapper(aliases_path)

    def adapt_table(
        self,
        source: pd.DataFrame,
        table: str,
        explicit_mapping: dict[str, str] | None = None,
    ) -> AdaptationResult:
        if table not in self.contract["tables"]:
            raise ValueError(f"Unknown canonical table: {table}")
        definition = self.contract["tables"][table]
        canonical = set(definition["columns"])
        explicit_mapping = explicit_mapping or {}
        proposals = self.mapper.propose(list(source.columns), canonical)
        mapping = dict(explicit_mapping)
        warnings = []
        for proposal in proposals:
            if proposal.source_column in mapping:
                continue
            if proposal.confidence in {"exact", "alias"}:
                mapping[proposal.source_column] = proposal.canonical_column  # type: ignore[assignment]
            elif proposal.confidence == "ambiguous":
                raise ValueError(
                    f"Ambiguous mapping for {proposal.source_column}: {proposal.candidates}"
                )
            else:
                warnings.append(f"Unmapped source column ignored: {proposal.source_column}")

        frame = source.rename(columns=mapping).copy()
        frame = frame[[column for column in frame.columns if column in canonical]]
        generated = []
        for column, rule in definition["columns"].items():
            if column not in frame and rule.get("generate_if_missing"):
                grain = definition["grain"]
                if not set(grain) <= set(frame.columns):
                    raise ValueError(f"Cannot generate {column}; missing grain columns {grain}")
                frame[column] = frame.apply(
                    lambda row: f"GEN-{hashlib.sha256('|'.join(str(row[key]) for key in grain).encode()).hexdigest()[:20]}",
                    axis=1,
                )
                generated.append(column)

        missing_required = [
            column for column, rule in definition["columns"].items()
            if rule.get("external_required") and column not in frame
        ]
        if missing_required:
            raise ValueError(f"Missing externally required fields for {table}: {missing_required}")
        frame = frame[[column for column in definition["columns"] if column in frame.columns]]
        return AdaptationResult(table, frame, mapping, generated, warnings)

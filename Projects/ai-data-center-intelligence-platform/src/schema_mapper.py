from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


@dataclass(frozen=True)
class MappingProposal:
    source_column: str
    canonical_column: str | None
    confidence: str
    candidates: tuple[str, ...] = ()


class SchemaMapper:
    def __init__(self, aliases_path: Path | str) -> None:
        aliases = json.loads(Path(aliases_path).read_text(encoding="utf-8"))
        self.aliases = {
            canonical: {normalize_name(alias) for alias in values}
            for canonical, values in aliases.items()
        }

    def propose(self, source_columns: list[str], canonical_columns: set[str]) -> list[MappingProposal]:
        proposals = []
        for source in source_columns:
            normalized = normalize_name(source)
            candidates = sorted(
                canonical for canonical in canonical_columns
                if normalized == normalize_name(canonical) or normalized in self.aliases.get(canonical, set())
            )
            if len(candidates) == 1:
                confidence = "exact" if normalized == normalize_name(candidates[0]) else "alias"
                proposals.append(MappingProposal(source, candidates[0], confidence))
            elif len(candidates) > 1:
                proposals.append(MappingProposal(source, None, "ambiguous", tuple(candidates)))
            else:
                proposals.append(MappingProposal(source, None, "unmapped"))
        return proposals


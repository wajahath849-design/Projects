from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.dataset_adapter import DatasetAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Map external CSV files into the canonical model.")
    parser.add_argument("input", type=Path, help="Folder containing external CSV files")
    parser.add_argument("output", type=Path, help="Output folder for canonical CSV files")
    parser.add_argument("--mapping", type=Path, help="Optional YAML mapping file")
    args = parser.parse_args()
    mapping = yaml.safe_load(args.mapping.read_text(encoding="utf-8")) if args.mapping else {}
    adapter = DatasetAdapter(settings.contract_path, settings.project_root / "adapters/default_aliases.json")
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"adapted": [], "skipped": [], "warnings": []}
    for table in adapter.contract["tables"]:
        configured = mapping.get("tables", {}).get(table, {})
        source_name = configured.get("source_file", f"{table}.csv")
        source_path = args.input / source_name
        if not source_path.exists():
            report["skipped"].append(table)
            continue
        result = adapter.adapt_table(pd.read_csv(source_path), table, configured.get("columns"))
        result.frame.to_csv(args.output / f"{table}.csv", index=False)
        report["adapted"].append(table)
        report["warnings"].extend(result.warnings)
    (args.output / "adaptation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

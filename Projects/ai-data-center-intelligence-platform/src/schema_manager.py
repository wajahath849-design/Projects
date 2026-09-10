"""Contract-driven canonical schema and module validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    enabled_modules: list[str] = field(default_factory=list)
    disabled_modules: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


class SchemaManager:
    def __init__(self, contract_path: Path | str) -> None:
        self.contract_path = Path(contract_path)
        self.contract = json.loads(self.contract_path.read_text(encoding="utf-8"))

    @property
    def table_names(self) -> set[str]:
        return set(self.contract["tables"])

    def detect_modules(self, available_tables: set[str]) -> tuple[list[str], list[str]]:
        enabled, disabled = [], []
        for module, definition in self.contract["modules"].items():
            required = set(definition["required_tables"])
            (enabled if required <= available_tables else disabled).append(module)
        return enabled, disabled

    def validate_directory(self, directory: Path | str) -> ValidationResult:
        directory = Path(directory)
        paths = {
            path.stem: path
            for path in directory.glob("*.csv")
            if path.stem in self.table_names
        }
        tables = {
            name: pd.read_csv(path, low_memory=False) for name, path in paths.items()
        }
        return self.validate_tables(tables)

    def validate_tables(self, tables: dict[str, pd.DataFrame]) -> ValidationResult:
        result = ValidationResult()
        available = set(tables)
        unknown = available - self.table_names
        if unknown:
            result.warnings.append(f"Unknown tables ignored: {sorted(unknown)}")

        result.enabled_modules, result.disabled_modules = self.detect_modules(available)
        for module in result.disabled_modules:
            required = set(self.contract["modules"][module]["required_tables"])
            missing = sorted(required - available)
            result.warnings.append(f"Module '{module}' disabled; missing tables: {missing}")

        for table_name, frame in tables.items():
            if table_name not in self.contract["tables"]:
                continue
            self._validate_table(table_name, frame, result)

        self._validate_foreign_keys(tables, result)
        return result

    def _validate_table(
        self, table_name: str, frame: pd.DataFrame, result: ValidationResult
    ) -> None:
        definition = self.contract["tables"][table_name]
        expected = list(definition["columns"])
        missing = [column for column in expected if column not in frame.columns]
        extra = [column for column in frame.columns if column not in expected]
        if missing:
            result.errors.append(f"{table_name}: missing canonical columns {missing}")
        if extra:
            result.errors.append(f"{table_name}: unexpected columns {extra}")
        if missing:
            return
        if list(frame.columns) != expected:
            result.warnings.append(f"{table_name}: canonical column order differs")

        for column, rule in definition["columns"].items():
            series = frame[column]
            if not rule["nullable"] and series.isna().any():
                result.errors.append(f"{table_name}.{column}: null values are not allowed")
            self._validate_column_type(table_name, column, series, rule, result)
            if "allowed_values" in rule:
                invalid = set(series.dropna().astype(str)) - set(rule["allowed_values"])
                if invalid:
                    result.errors.append(
                        f"{table_name}.{column}: unexpected values {sorted(invalid)}"
                    )

        primary_key = definition["primary_key"]
        if frame.duplicated(primary_key).any():
            result.errors.append(f"{table_name}: duplicate primary key {primary_key}")
        grain = definition["grain"]
        if frame.duplicated(grain).any():
            result.errors.append(f"{table_name}: duplicate grain {grain}")

    @staticmethod
    def _validate_column_type(
        table: str,
        column: str,
        series: pd.Series,
        rule: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        kind = rule["type"]
        if kind in {"number", "integer"}:
            converted = pd.to_numeric(series, errors="coerce")
            invalid_type = series.notna() & converted.isna()
            if invalid_type.any():
                result.errors.append(f"{table}.{column}: contains non-numeric values")
                return
            if kind == "integer" and ((converted.dropna() % 1) != 0).any():
                result.errors.append(f"{table}.{column}: contains non-integer values")
            if "minimum" in rule and (converted.dropna() < rule["minimum"]).any():
                result.errors.append(f"{table}.{column}: values below {rule['minimum']}")
            if "maximum" in rule and (converted.dropna() > rule["maximum"]).any():
                result.errors.append(f"{table}.{column}: values above {rule['maximum']}")
        elif kind in {"date", "datetime"}:
            converted = pd.to_datetime(series, errors="coerce")
            if (series.notna() & converted.isna()).any():
                result.errors.append(f"{table}.{column}: contains invalid {kind} values")
        elif kind == "string":
            empty = series.notna() & series.astype(str).str.strip().eq("")
            if empty.any():
                result.errors.append(f"{table}.{column}: contains empty strings")

    def _validate_foreign_keys(
        self, tables: dict[str, pd.DataFrame], result: ValidationResult
    ) -> None:
        for table_name, frame in tables.items():
            if table_name not in self.contract["tables"]:
                continue
            for relation in self.contract["tables"][table_name]["foreign_keys"]:
                parent_name = relation["references_table"]
                if parent_name not in tables:
                    result.warnings.append(
                        f"{table_name}: foreign key not checked because '{parent_name}' is absent"
                    )
                    continue
                child_columns = relation["columns"]
                parent_columns = relation["references_columns"]
                child_keys = pd.MultiIndex.from_frame(frame[child_columns])
                parent_keys = pd.MultiIndex.from_frame(tables[parent_name][parent_columns])
                orphan_count = int((~child_keys.isin(parent_keys)).sum())
                if orphan_count:
                    result.errors.append(
                        f"{table_name}: {orphan_count} orphan rows for foreign key "
                        f"{child_columns} -> {parent_name}.{parent_columns}"
                    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate canonical CSV tables.")
    parser.add_argument("directory", type=Path, nargs="?", default=Path("data/cleaned_generated"))
    parser.add_argument(
        "--contract", type=Path, default=Path("analytics/canonical_data_contract.json")
    )
    args = parser.parse_args()
    result = SchemaManager(args.contract).validate_directory(args.directory)
    print(json.dumps({
        "is_valid": result.is_valid,
        "enabled_modules": result.enabled_modules,
        "disabled_modules": result.disabled_modules,
        "warnings": result.warnings,
        "errors": result.errors,
    }, indent=2))
    raise SystemExit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()

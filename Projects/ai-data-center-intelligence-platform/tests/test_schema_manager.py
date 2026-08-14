import json
from pathlib import Path

import pandas as pd
import pytest

from src.schema_manager import SchemaManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT / "analytics" / "canonical_data_contract.json"


@pytest.fixture(scope="module")
def manager() -> SchemaManager:
    return SchemaManager(CONTRACT_PATH)


@pytest.fixture(scope="module")
def canonical_tables() -> dict[str, pd.DataFrame]:
    directory = PROJECT_ROOT / "data" / "cleaned_generated"
    return {path.stem: pd.read_csv(path, low_memory=False) for path in directory.glob("*.csv")}


def test_contract_is_complete_and_self_consistent(manager) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert set(contract["tables"]) == {
        "facilities", "servers", "server_metrics", "power_metrics",
        "network_metrics", "uptime_incidents",
    }
    for table, definition in contract["tables"].items():
        columns = set(definition["columns"])
        assert set(definition["primary_key"]) <= columns, table
        assert set(definition["grain"]) <= columns, table
        for relation in definition["foreign_keys"]:
            assert relation["references_table"] in contract["tables"]


def test_complete_canonical_dataset_is_valid(manager, canonical_tables) -> None:
    result = manager.validate_tables(canonical_tables)
    assert result.is_valid, result.errors
    assert set(result.enabled_modules) == {
        "inventory", "server_performance", "energy", "network", "reliability"
    }
    assert result.disabled_modules == []


def test_power_only_dataset_enables_energy_without_crashing(manager, canonical_tables) -> None:
    subset = {name: canonical_tables[name] for name in ("facilities", "power_metrics")}
    result = manager.validate_tables(subset)
    assert result.is_valid
    assert result.enabled_modules == ["energy"]
    assert set(result.disabled_modules) == {
        "inventory", "server_performance", "network", "reliability"
    }


def test_missing_optional_module_is_warning_not_error(manager, canonical_tables) -> None:
    result = manager.validate_tables({"facilities": canonical_tables["facilities"]})
    assert result.is_valid
    assert result.disabled_modules
    assert result.warnings


def test_missing_canonical_column_fails(manager, canonical_tables) -> None:
    broken = canonical_tables["power_metrics"].drop(columns=["pue"])
    result = manager.validate_tables({"facilities": canonical_tables["facilities"], "power_metrics": broken})
    assert not result.is_valid
    assert any("missing canonical columns" in error for error in result.errors)


def test_out_of_range_value_fails(manager, canonical_tables) -> None:
    broken = canonical_tables["network_metrics"].head(2).copy()
    broken.loc[broken.index[0], "packet_loss_pct"] = 99
    result = manager.validate_tables({"facilities": canonical_tables["facilities"], "network_metrics": broken})
    assert not result.is_valid
    assert any("values above 5" in error for error in result.errors)


def test_orphan_foreign_key_fails(manager, canonical_tables) -> None:
    broken = canonical_tables["servers"].head(2).copy()
    broken.loc[broken.index[0], "facility_id"] = "UNKNOWN"
    result = manager.validate_tables({"facilities": canonical_tables["facilities"], "servers": broken})
    assert not result.is_valid
    assert any("orphan rows" in error for error in result.errors)


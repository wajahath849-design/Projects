import json
from pathlib import Path

import yaml

from scripts.validate_kpis import SQL, validate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_kpi_catalog_references_defined_metrics() -> None:
    definitions = yaml.safe_load((PROJECT_ROOT / "analytics" / "metric_definitions.yaml").read_text())
    catalog = yaml.safe_load((PROJECT_ROOT / "analytics" / "kpi_catalog.yaml").read_text())
    names = set(definitions["metrics"])
    referenced = set(catalog["primary_kpis"])
    for values in catalog["drivers"].values():
        referenced.update(values)
    assert referenced <= names


def test_every_metric_has_sql_validation() -> None:
    definitions = yaml.safe_load((PROJECT_ROOT / "analytics" / "metric_definitions.yaml").read_text())
    names = set(definitions["metrics"])
    assert set(SQL) <= names
    assert names - set(SQL) == {
        "modeled_energy_kwh", "modeled_energy_cost", "modeled_cooling_cost",
        "modeled_carbon_tonnes", "efficiency_opportunity_score",
    }


def test_sql_and_python_kpis_reconcile() -> None:
    report = validate(PROJECT_ROOT / "database" / "datacenter.db", PROJECT_ROOT / "data" / "processed")
    assert report["all_passed"], json.dumps(report["metrics"], indent=2)

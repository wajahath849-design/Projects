import json
from pathlib import Path

from scripts.build_powerbi_project import (
    EXTRA_DATE_COLUMNS,
    MEASURE_DEFINITIONS,
    SNAPSHOT_TABLES,
    TABLES,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POWERBI = PROJECT_ROOT / "powerbi"
GENERATED = POWERBI / "PBI"
PROJECT_NAME = "DataCenter Executive Dashboard"


def test_all_power_query_sources_exist() -> None:
    names = {path.stem for path in (POWERBI / "foundation" / "PowerQuery").glob("*.pq")}
    assert names == {
        "DataRoot", "DimFacility", "DimServer", "FactServerMetrics",
        "FactPowerMetrics", "FactNetworkMetrics", "FactIncidents",
        "FactSystemLogs", "FactAlerts", "FactMaintenanceActions",
        "FactAnomalies", "FactServerRisk", "FactFacilityHealth",
        "FactCostCarbon", "FactIncidentImpact", "FactLiveOperationsSnapshot",
    }


def test_foundational_dax_contains_canonical_measures() -> None:
    dax = (POWERBI / "foundation" / "DAX" / "measures.dax").read_text(encoding="utf-8")
    required = [
        "Average PUE", "Total Power Draw", "Total Cooling Cost", "Total Downtime",
        "Incident Count", "Active Server Count", "Average CPU Utilization",
        "Average Memory Utilization", "Average Network Latency", "Average Packet Loss",
        "Network Availability", "Downtime per Server", "Incident Rate per 100 Servers",
        "Year-over-Year PUE Change", "Year-over-Year Cooling Cost Change",
        "Year-over-Year Downtime Change",
        "Log Count", "Critical Alert Count", "Anomaly Count", "Critical Anomaly Count",
        "Maintenance Action Count", "MTTR Minutes", "Average Server Risk Score",
        "High Risk Server Count", "Average Facility Health Score", "Latest Data Date",
    ]
    assert all(f"{name} =" in dax for name in required)


def test_date_table_uses_canonical_dataset_range() -> None:
    dax = (POWERBI / "foundation" / "DAX" / "calculated_tables.dax").read_text(encoding="utf-8")
    assert "DATE(2015, 1, 1)" in dax
    assert "DATE(2025, 12, 31)" in dax


def test_power_query_uses_verified_processed_data() -> None:
    parameter = (POWERBI / "foundation" / "PowerQuery" / "DataRoot.pq").read_text(encoding="utf-8")
    assert "data\\\\processed" in parameter


def test_generated_pbip_has_seven_populated_pages_and_model_files() -> None:
    root = GENERATED
    assert (root / f"{PROJECT_NAME}.pbip").exists()
    semantic = root / f"{PROJECT_NAME}.SemanticModel" / "definition"
    assert (semantic / "model.tmdl").exists()
    assert (semantic / "relationships.tmdl").exists()
    assert len(list((semantic / "tables").glob("*.tmdl"))) == 17
    pages = root / f"{PROJECT_NAME}.Report" / "definition" / "pages"
    page_folders = [path for path in pages.iterdir() if path.is_dir()]
    assert len(page_folders) == 7
    assert sum(1 for _ in pages.rglob("visual.json")) == 223
    assert all(sum(1 for _ in folder.rglob("visual.json")) >= 31 for folder in page_folders)


def test_generated_model_has_expected_relationships() -> None:
    path = GENERATED / f"{PROJECT_NAME}.SemanticModel" / "definition" / "relationships.tmdl"
    text = path.read_text(encoding="utf-8")
    assert text.count("relationship ") == 30
    assert "isActive: false" in text


def test_report_pages_use_opaque_internal_ids_and_registered_theme() -> None:
    report_root = GENERATED / f"{PROJECT_NAME}.Report" / "definition"
    pages = json.loads((report_root / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert all(len(name) == 20 and name.isalnum() for name in pages["pageOrder"])
    report = json.loads((report_root / "report.json").read_text(encoding="utf-8"))
    theme = report["themeCollection"]["customTheme"]
    assert theme["name"] == "DataCenterExecutive-20260904.json"
    resource = report_root.parent / "StaticResources" / "RegisteredResources" / theme["name"]
    assert resource.exists()


def test_every_page_has_required_visual_families() -> None:
    report_root = GENERATED / f"{PROJECT_NAME}.Report" / "definition"
    page_order = json.loads(
        (report_root / "pages" / "pages.json").read_text(encoding="utf-8")
    )["pageOrder"]
    for page_id in page_order:
        visual_types = {
            json.loads(path.read_text(encoding="utf-8"))["visual"]["visualType"]
            for path in (report_root / "pages" / page_id / "visuals").rglob("visual.json")
        }
        assert {"textbox", "slicer", "card", "tableEx"} <= visual_types
        assert visual_types & {"lineChart", "clusteredBarChart"}


def test_every_page_has_executive_chrome() -> None:
    report_root = GENERATED / f"{PROJECT_NAME}.Report" / "definition"
    page_order = json.loads(
        (report_root / "pages" / "pages.json").read_text(encoding="utf-8")
    )["pageOrder"]
    for page_id in page_order:
        visuals = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (report_root / "pages" / page_id / "visuals").rglob("visual.json")
        ]
        text_values = json.dumps(visuals)
        assert "Data Center Intelligence" in text_values
        assert "Overview" in text_values and "Cost & Carbon" in text_values
        assert any(item["position"]["width"] == 1600 for item in visuals)


def test_all_visual_bindings_resolve_to_model_fields() -> None:
    contract = json.loads(
        (PROJECT_ROOT / "analytics" / "canonical_data_contract.json").read_text(
            encoding="utf-8"
        )
    )
    known = {
        table_name: set(contract["tables"][source_name]["columns"])
        for table_name, source_name in TABLES.items()
    }
    for table_name, (date_column, _) in EXTRA_DATE_COLUMNS.items():
        known[table_name].add(date_column)
    known.update({name: set(columns) for name, columns in SNAPSHOT_TABLES.items()})
    known["DimDate"] = {
        "Date", "Year", "Quarter Number", "Quarter", "Month Number", "Month",
        "Month Year", "Year Month", "Weekday Number", "Weekday",
    }
    known["_Measures"] = {name for name, *_ in MEASURE_DEFINITIONS}

    report_pages = (
        GENERATED / f"{PROJECT_NAME}.Report" / "definition" / "pages"
    )
    unresolved: list[str] = []
    for path in report_pages.rglob("visual.json"):
        stack: list[object] = [json.loads(path.read_text(encoding="utf-8"))]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for expression_type in ("Column", "Measure"):
                    expression = node.get(expression_type)
                    if not isinstance(expression, dict):
                        continue
                    table_name = expression.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    property_name = expression.get("Property")
                    if table_name not in known or property_name not in known[table_name]:
                        unresolved.append(f"{path.name}: {table_name}.{property_name}")
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    assert unresolved == []


def test_advanced_snapshot_tables_are_governed_and_noncausal() -> None:
    processed = PROJECT_ROOT / "data" / "processed"
    cost = (processed / "powerbi_cost_carbon_snapshot.csv").read_text(encoding="utf-8")
    impact = (processed / "powerbi_incident_impact_snapshot.csv").read_text(encoding="utf-8")
    live = (processed / "powerbi_live_operations_snapshot.csv").read_text(encoding="utf-8")
    assert "assumptions_are_synthetic" in cost and "cost-carbon-v1" in cost
    assert "descriptive_before_after" in impact and "incident-impact-v1" in impact
    assert "live-operations-v1" in live
    assert "causal" not in impact.lower()

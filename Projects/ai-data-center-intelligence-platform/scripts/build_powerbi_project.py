"""Generate a source-controlled Power BI Project foundation from canonical files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


TABLES = {
    "DimFacility": "facilities",
    "DimServer": "servers",
    "FactServerMetrics": "server_metrics",
    "FactPowerMetrics": "power_metrics",
    "FactNetworkMetrics": "network_metrics",
    "FactIncidents": "uptime_incidents",
}

TYPE_MAP = {
    "string": "string",
    "integer": "int64",
    "number": "double",
    "date": "dateTime",
    "datetime": "dateTime",
}

MEASURE_DEFINITIONS = [
    ("Server Count", "DISTINCTCOUNT(DimServer[server_id])", "#,0", "Inventory"),
    ("Active Server Count", 'CALCULATE(DISTINCTCOUNT(DimServer[server_id]), KEEPFILTERS(DimServer[status] = "active"))', "#,0", "Inventory"),
    ("Average PUE", "AVERAGE(FactPowerMetrics[pue])", "0.000", "Energy"),
    ("Total Power Draw", "SUM(FactPowerMetrics[power_draw_kw])", "#,0.00", "Energy"),
    ("Total IT Load", "SUM(FactPowerMetrics[it_load_kw])", "#,0.00", "Energy"),
    ("Total Cooling Power", "SUM(FactPowerMetrics[cooling_power_kw])", "#,0.00", "Energy"),
    ("Total Cooling Cost", "SUM(FactPowerMetrics[cooling_cost])", "#,0.00", "Energy"),
    ("Average CPU Utilization", "AVERAGE(FactServerMetrics[cpu_utilization_pct])", "0.00", "Infrastructure"),
    ("Average Memory Utilization", "AVERAGE(FactServerMetrics[memory_utilization_pct])", "0.00", "Infrastructure"),
    ("Average Disk Utilization", "AVERAGE(FactServerMetrics[disk_utilization_pct])", "0.00", "Infrastructure"),
    ("Average Server Network Utilization", "AVERAGE(FactServerMetrics[network_utilization_pct])", "0.00", "Infrastructure"),
    ("Average Network Latency", "AVERAGE(FactNetworkMetrics[latency_ms])", "0.00", "Network"),
    ("Average Packet Loss", "AVERAGE(FactNetworkMetrics[packet_loss_pct])", "0.000", "Network"),
    ("Average Throughput", "AVERAGE(FactNetworkMetrics[throughput_mbps])", "#,0.00", "Network"),
    ("Network Availability", "AVERAGE(FactNetworkMetrics[network_availability_pct])", "0.0000", "Network"),
    ("Total Downtime", "SUM(FactIncidents[downtime_minutes])", "#,0", "Reliability"),
    ("Incident Count", "DISTINCTCOUNT(FactIncidents[incident_id])", "#,0", "Reliability"),
    ("Downtime per Server", "DIVIDE([Total Downtime], [Server Count])", "0.00", "Reliability"),
    ("Incident Rate per 100 Servers", "DIVIDE([Incident Count], [Server Count]) * 100", "0.00", "Reliability"),
    ("Visible Days", "DISTINCTCOUNT(DimDate[Date])", "#,0", "Reliability"),
    ("Operational Availability", "VAR PotentialServerMinutes = [Server Count] * [Visible Days] * 1440 RETURN 100 * (1 - DIVIDE([Total Downtime], PotentialServerMinutes))", "0.0000", "Reliability"),
    ("Previous Year Average PUE", "CALCULATE([Average PUE], DATEADD(DimDate[Date], -1, YEAR))", "0.000", "Time Intelligence"),
    ("Year-over-Year PUE Change", "DIVIDE([Average PUE] - [Previous Year Average PUE], [Previous Year Average PUE])", "0.00%", "Time Intelligence"),
    ("Previous Year Cooling Cost", "CALCULATE([Total Cooling Cost], DATEADD(DimDate[Date], -1, YEAR))", "#,0.00", "Time Intelligence"),
    ("Year-over-Year Cooling Cost Change", "DIVIDE([Total Cooling Cost] - [Previous Year Cooling Cost], [Previous Year Cooling Cost])", "0.00%", "Time Intelligence"),
    ("Previous Year Downtime", "CALCULATE([Total Downtime], DATEADD(DimDate[Date], -1, YEAR))", "#,0", "Time Intelligence"),
    ("Year-over-Year Downtime Change", "DIVIDE([Total Downtime] - [Previous Year Downtime], [Previous Year Downtime])", "0.00%", "Time Intelligence"),
]


def indent(text: str, tabs: int) -> str:
    prefix = "\t" * tabs
    return "\n".join(prefix + line if line else "" for line in text.splitlines())


def table_tmdl(
    table_name: str, source_name: str, definition: dict, power_query: str, data_root: Path
) -> str:
    query = re.sub(
        r'DataRoot\s*&\s*"\\\\([^\"]+)"',
        lambda match: f'"{data_root.as_posix()}/{match.group(1)}"',
        power_query,
    )
    lines = [f"table {table_name}", ""]
    columns = dict(definition["columns"])
    if table_name == "FactIncidents":
        columns["incident_date"] = {"type": "date", "nullable": False}
    for column, rule in columns.items():
        lines.extend([
            f"\tcolumn {column}",
            f"\t\tdataType: {TYPE_MAP[rule['type']]}",
            f"\t\tisNullable: {str(bool(rule.get('nullable', True))).lower()}",
            "\t\tsummarizeBy: none",
            f"\t\tsourceColumn: {column}",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
            "",
        ])
    lines.extend([
        f"\tpartition {table_name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        indent(query, 4),
        "",
    ])
    return "\n".join(lines)


def date_table_tmdl() -> str:
    columns = [
        ("Date", "General Date"), ("Year", "0"), ("Quarter Number", "0"),
        ("Quarter", None), ("Month Number", "0"), ("Month", None),
        ("Month Year", None), ("Year Month", None), ("Weekday Number", "0"),
        ("Weekday", None),
    ]
    lines = ["table DimDate", ""]
    for name, format_string in columns:
        lines.append(f"\tcolumn '{name}'" if " " in name else f"\tcolumn {name}")
        if format_string:
            lines.append(f"\t\tformatString: {format_string}")
        lines.extend(["\t\tsummarizeBy: none", f"\t\tsourceColumn: [{name}]", ""])
    dax = """ADDCOLUMNS(
    CALENDAR(DATE(2015, 1, 1), DATE(2025, 12, 31)),
    \"Year\", YEAR([Date]),
    \"Quarter Number\", QUARTER([Date]),
    \"Quarter\", \"Q\" & FORMAT(QUARTER([Date]), \"0\"),
    \"Month Number\", MONTH([Date]),
    \"Month\", FORMAT([Date], \"MMM\"),
    \"Month Year\", FORMAT([Date], \"MMM yyyy\"),
    \"Year Month\", FORMAT([Date], \"yyyy-MM\"),
    \"Weekday Number\", WEEKDAY([Date], 2),
    \"Weekday\", FORMAT([Date], \"ddd\")
)"""
    lines.extend(["\tpartition DimDate = calculated", "\t\tmode: import", "\t\tsource =", indent(dax, 4), ""])
    return "\n".join(lines)


def measures_tmdl() -> str:
    lines = ["table _Measures", "", "\tcolumn Placeholder", "\t\tdataType: string", "\t\tisHidden", "\t\tsummarizeBy: none", "\t\tsourceColumn: [Placeholder]", ""]
    for name, expression, format_string, folder in MEASURE_DEFINITIONS:
        quoted = f"'{name}'" if " " in name or "-" in name else name
        lines.extend([f"\tmeasure {quoted} = {expression}", f"\t\tformatString: {format_string}", f"\t\tdisplayFolder: {folder}", ""])
    lines.extend(["\tpartition _Measures = calculated", "\t\tmode: import", '"\t\tsource = DATATABLE(\"Placeholder\", STRING, {{\"Measures\"}})"'.strip('"'), ""])
    return "\n".join(lines)


def build(project_root: Path, output_root: Path) -> Path:
    contract = json.loads((project_root / "analytics" / "canonical_data_contract.json").read_text(encoding="utf-8"))
    project_name = "DataCenter Operations Foundation"
    semantic = output_root / f"{project_name}.SemanticModel"
    report = output_root / f"{project_name}.Report"
    if output_root.exists():
        shutil.rmtree(output_root)
    (semantic / "definition" / "tables").mkdir(parents=True)
    (report / "definition" / "pages").mkdir(parents=True)

    pbip = {"version": "1.0", "artifacts": [{"report": {"path": f"{project_name}.Report"}}], "settings": {}}
    (output_root / f"{project_name}.pbip").write_text(json.dumps(pbip, indent=2), encoding="utf-8")
    (semantic / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (semantic / "definition" / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n", encoding="utf-8")

    refs = ["DimDate", "DimFacility", "DimServer", "FactServerMetrics", "FactPowerMetrics", "FactNetworkMetrics", "FactIncidents", "_Measures"]
    model = "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\n" + "\n".join(f"ref table {name}" for name in refs) + "\n"
    (semantic / "definition" / "model.tmdl").write_text(model, encoding="utf-8")

    data_root = (project_root / "data" / "processed").resolve()
    for table_name, source_name in TABLES.items():
        query = (project_root / "powerbi" / "foundation" / "PowerQuery" / f"{table_name}.pq").read_text(encoding="utf-8")
        content = table_tmdl(table_name, source_name, contract["tables"][source_name], query, data_root)
        (semantic / "definition" / "tables" / f"{table_name}.tmdl").write_text(content, encoding="utf-8")
    (semantic / "definition" / "tables" / "DimDate.tmdl").write_text(date_table_tmdl(), encoding="utf-8")
    (semantic / "definition" / "tables" / "_Measures.tmdl").write_text(measures_tmdl(), encoding="utf-8")

    relationships = """relationship rel_facility_server
\tfromColumn: DimServer.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_facility_power
\tfromColumn: FactPowerMetrics.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_facility_network
\tfromColumn: FactNetworkMetrics.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_facility_incidents
\tfromColumn: FactIncidents.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_server_metrics
\tfromColumn: FactServerMetrics.server_id
\ttoColumn: DimServer.server_id

relationship rel_server_incidents
\tisActive: false
\tfromColumn: FactIncidents.server_id
\ttoColumn: DimServer.server_id

relationship rel_date_server_metrics
\tfromColumn: FactServerMetrics.timestamp
\ttoColumn: DimDate.Date

relationship rel_date_power
\tfromColumn: FactPowerMetrics.timestamp
\ttoColumn: DimDate.Date

relationship rel_date_network
\tfromColumn: FactNetworkMetrics.timestamp
\ttoColumn: DimDate.Date

relationship rel_date_incidents
\tfromColumn: FactIncidents.incident_date
\ttoColumn: DimDate.Date
"""
    (semantic / "definition" / "relationships.tmdl").write_text(relationships, encoding="utf-8")

    (report / "definition.pbir").write_text(json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": f"../{project_name}.SemanticModel"}}}, indent=2), encoding="utf-8")
    (report / "definition" / "version.json").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2), encoding="utf-8")
    report_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY25SU12",
                "reportVersionAtImport": {
                    "visual": "2.5.0",
                    "report": "3.1.0",
                    "page": "2.3.0"
                },
                "type": "SharedResources"
            }
        },
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [
                    {
                        "name": "CY25SU12",
                        "path": "BaseThemes/CY25SU12.json",
                        "type": "BaseTheme"
                    }
                ]
            }
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultFilterActionIsDataFilter": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "allowInlineExploration": True,
            "useEnhancedTooltips": True
        }
    }
    (report / "definition" / "report.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")
    # PBIR page names are internal opaque identifiers, not display-name slugs.
    page_defs = [
        ("dce0f001202608140001", "Executive Operations Overview"),
        ("dce0f001202608140002", "Infrastructure Performance"),
        ("dce0f001202608140003", "Energy & Reliability"),
    ]
    pages = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json", "pageOrder": [name for name, _ in page_defs], "activePageName": page_defs[0][0]}
    (report / "definition" / "pages" / "pages.json").write_text(json.dumps(pages, indent=2), encoding="utf-8")
    for name, display in page_defs:
        folder = report / "definition" / "pages" / name
        folder.mkdir()
        page = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json", "name": name, "displayName": display, "displayOption": "FitToPage", "height": 900, "width": 1600}
        (folder / "page.json").write_text(json.dumps(page, indent=2), encoding="utf-8")
    return output_root / f"{project_name}.pbip"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Step 7 PBIP foundation.")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("powerbi/PBI"))
    args = parser.parse_args()
    path = build(args.project_root.resolve(), args.output.resolve())
    print(path)


if __name__ == "__main__":
    main()

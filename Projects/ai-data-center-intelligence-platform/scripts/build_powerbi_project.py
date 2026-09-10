"""Generate a source-controlled Power BI Project foundation from canonical files."""

from __future__ import annotations

import argparse
import hashlib
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
    "FactSystemLogs": "system_logs",
    "FactAlerts": "alerts",
    "FactMaintenanceActions": "maintenance_actions",
    "FactAnomalies": "detected_anomalies",
    "FactServerRisk": "server_failure_risk",
    "FactFacilityHealth": "facility_health_scores",
}

SNAPSHOT_TABLES = {
    "FactCostCarbon": {
        "snapshot_date": "date", "year": "integer", "month_label": "string",
        "facility_id": "string", "facility_name": "string", "observation_days": "integer",
        "modeled_energy_kwh": "number", "modeled_it_energy_kwh": "number",
        "modeled_cooling_energy_kwh": "number", "modeled_energy_cost_usd": "number",
        "modeled_it_cost_usd": "number", "modeled_cooling_cost_usd": "number",
        "modeled_carbon_tonnes": "number", "modeled_it_carbon_tonnes": "number",
        "modeled_cooling_carbon_tonnes": "number", "average_pue": "number",
        "price_per_kwh": "number", "grams_co2e_per_kwh": "number",
        "efficiency_opportunity_score": "number", "currency": "string",
        "pricing_basis": "string", "price_source": "string",
        "carbon_methodology": "string", "carbon_source": "string",
        "assumptions_are_synthetic": "boolean", "snapshot_version": "string",
        "source_period": "string",
    },
    "FactIncidentImpact": {
        "incident_id": "string", "incident_date": "date", "facility_id": "string",
        "facility_name": "string", "server_id": "string", "severity": "string",
        "root_cause": "string", "status": "string", "downtime_minutes": "integer",
        "during_pue": "number", "during_latency_ms": "number",
        "during_packet_loss_pct": "number", "during_network_availability_pct": "number",
        "before_pue": "number", "after_pue": "number", "before_latency_ms": "number",
        "after_latency_ms": "number", "before_packet_loss_pct": "number",
        "after_packet_loss_pct": "number", "before_network_availability_pct": "number",
        "after_network_availability_pct": "number", "change_pue_pct": "number",
        "change_latency_ms_pct": "number", "change_packet_loss_pct_pct": "number",
        "change_network_availability_pct_pct": "number",
        "modeled_downtime_cost_exposure_usd": "number",
        "comparison_window_days": "integer", "claim_level": "string",
        "is_synthetic": "boolean", "snapshot_version": "string",
    },
    "FactLiveOperationsSnapshot": {
        "simulation_session_id": "string", "scenario_name": "string",
        "session_status": "string", "snapshot_timestamp": "datetime",
        "facility_id": "string", "facility_name": "string", "health_score": "number",
        "energy_efficiency_score": "number", "reliability_score": "number",
        "network_health_score": "number", "infrastructure_score": "number",
        "alert_score": "number", "anomaly_score": "number",
        "active_alert_count": "integer", "active_anomaly_count": "integer",
        "data_completeness_pct": "number", "method_version": "string",
        "is_synthetic": "boolean", "snapshot_version": "string",
    },
}

EXTRA_DATE_COLUMNS = {
    "FactIncidents": ("incident_date", "start_time"),
    "FactSystemLogs": ("log_date", "timestamp"),
    "FactAlerts": ("alert_date", "timestamp"),
    "FactMaintenanceActions": ("action_date", "timestamp"),
}

TYPE_MAP = {
    "string": "string",
    "integer": "int64",
    "number": "double",
    "date": "dateTime",
    "datetime": "dateTime",
    "boolean": "boolean",
}

VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"

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
    ("Log Count", "DISTINCTCOUNT(FactSystemLogs[log_id])", "#,0", "Incident Intelligence"),
    ("Error Log Count", 'CALCULATE([Log Count], KEEPFILTERS(FactSystemLogs[log_level] IN {"ERROR", "CRITICAL"}))', "#,0", "Incident Intelligence"),
    ("Critical Log Count", 'CALCULATE([Log Count], KEEPFILTERS(FactSystemLogs[log_level] = "CRITICAL"))', "#,0", "Incident Intelligence"),
    ("Alert Count", "DISTINCTCOUNT(FactAlerts[alert_id])", "#,0", "Incident Intelligence"),
    ("Critical Alert Count", 'CALCULATE([Alert Count], KEEPFILTERS(FactAlerts[severity] = "critical"))', "#,0", "Incident Intelligence"),
    ("Open Alert Count", 'CALCULATE([Alert Count], KEEPFILTERS(FactAlerts[status] = "open"))', "#,0", "Incident Intelligence"),
    ("Anomaly Count", "DISTINCTCOUNT(FactAnomalies[anomaly_id])", "#,0", "Incident Intelligence"),
    ("Critical Anomaly Count", 'CALCULATE([Anomaly Count], KEEPFILTERS(FactAnomalies[severity] = "critical"))', "#,0", "Incident Intelligence"),
    ("Maintenance Action Count", "DISTINCTCOUNT(FactMaintenanceActions[action_id])", "#,0", "Incident Intelligence"),
    ("MTTR Minutes", "AVERAGE(FactIncidents[downtime_minutes])", "0.00", "Reliability"),
    ("Average Server Risk Score", "AVERAGE(FactServerRisk[risk_score])", "0.00", "Predictive Operations"),
    ("High Risk Server Count", 'CALCULATE(DISTINCTCOUNT(FactServerRisk[server_id]), KEEPFILTERS(FactServerRisk[risk_level] IN {"high", "critical"}))', "#,0", "Predictive Operations"),
    ("Average Facility Health Score", "AVERAGE(FactFacilityHealth[health_score])", "0.00", "Predictive Operations"),
    ("Latest Data Date", "MAXX(UNION(SELECTCOLUMNS(FactPowerMetrics, \"DataDate\", FactPowerMetrics[timestamp]), SELECTCOLUMNS(FactNetworkMetrics, \"DataDate\", FactNetworkMetrics[timestamp]), SELECTCOLUMNS(FactServerMetrics, \"DataDate\", FactServerMetrics[timestamp])), [DataDate])", "General Date", "Data Quality"),
    ("Server Risk Observation Count", "COUNTROWS(FactServerRisk)", "#,0", "Predictive Operations"),
    ("Modeled Energy", "SUM(FactCostCarbon[modeled_energy_kwh])", "#,0", "Cost and Carbon"),
    ("Modeled Energy Cost", "SUM(FactCostCarbon[modeled_energy_cost_usd])", "$#,0", "Cost and Carbon"),
    ("Modeled Cooling Cost", "SUM(FactCostCarbon[modeled_cooling_cost_usd])", "$#,0", "Cost and Carbon"),
    ("Modeled Carbon", "SUM(FactCostCarbon[modeled_carbon_tonnes])", "#,0.00", "Cost and Carbon"),
    ("Average Energy Price", "AVERAGE(FactCostCarbon[price_per_kwh])", "$0.000", "Cost and Carbon"),
    ("Average Carbon Intensity", "AVERAGE(FactCostCarbon[grams_co2e_per_kwh])", "#,0.0", "Cost and Carbon"),
    ("Average Efficiency Opportunity Score", "AVERAGE(FactCostCarbon[efficiency_opportunity_score])", "0.0", "Cost and Carbon"),
    ("Incident Impact Count", "DISTINCTCOUNT(FactIncidentImpact[incident_id])", "#,0", "Reliability Impact"),
    ("Average Incident PUE Change", "AVERAGE(FactIncidentImpact[change_pue_pct])", "0.00", "Reliability Impact"),
    ("Average Incident Latency Change", "AVERAGE(FactIncidentImpact[change_latency_ms_pct])", "0.00", "Reliability Impact"),
    ("Modeled Downtime Cost Exposure", "SUM(FactIncidentImpact[modeled_downtime_cost_exposure_usd])", "$#,0", "Reliability Impact"),
    ("Live Facility Health Score", "AVERAGE(FactLiveOperationsSnapshot[health_score])", "0.0", "Live Operations"),
    ("Live Active Alert Count", "SUM(FactLiveOperationsSnapshot[active_alert_count])", "#,0", "Live Operations"),
    ("Live Data Completeness", "AVERAGE(FactLiveOperationsSnapshot[data_completeness_pct])", "0.0", "Live Operations"),
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
    if table_name in EXTRA_DATE_COLUMNS:
        date_column, _ = EXTRA_DATE_COLUMNS[table_name]
        columns[date_column] = {"type": "date", "nullable": False}
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


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ident(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]


def column(table_name: str, property_name: str) -> dict:
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table_name}},
            "Property": property_name,
        }
    }


def measure(table_name: str, property_name: str) -> dict:
    return {
        "Measure": {
            "Expression": {"SourceRef": {"Entity": table_name}},
            "Property": property_name,
        }
    }


def projection(field: dict, table_name: str, property_name: str) -> dict:
    return {
        "field": field,
        "queryRef": f"{table_name}.{property_name}",
        "nativeQueryRef": property_name,
    }


def position(x: int, y: int, width: int, height: int, z: int) -> dict:
    return {
        "x": x, "y": y, "z": z, "height": height, "width": width,
        "tabOrder": z,
    }


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def container_style(
    *,
    title_text: str | None = None,
    background: str = "#FFFFFF",
    border: str = "#DCE6F2",
    shadow: bool = True,
    padding: int = 10,
    radius: int = 8,
) -> dict:
    output = {
        "background": [{"properties": {
            "show": literal("true"),
            "color": {"solid": {"color": literal(f"'{background}'")}},
            "transparency": literal("0D"),
        }}],
        "border": [{"properties": {
            "show": literal("true"),
            "color": {"solid": {"color": literal(f"'{border}'")}},
            "radius": literal(f"{radius}D"),
            "width": literal("1D"),
        }}],
        "dropShadow": [{"properties": {
            "show": literal("true" if shadow else "false"),
            "preset": literal("'Bottom'"),
            "position": literal("'Outer'"),
            "color": {"solid": {"color": literal("'#64748B'")}},
            "transparency": literal("88L"),
            "shadowBlur": literal("8L"),
            "shadowDistance": literal("3L"),
            "angle": literal("90L"),
            "shadowSpread": literal("0L"),
        }}],
        "padding": [{"properties": {
            "top": literal(f"{padding}D"), "bottom": literal(f"{padding}D"),
            "left": literal(f"{padding}D"), "right": literal(f"{padding}D"),
        }}],
        "visualHeader": [{"properties": {"show": literal("false")}}],
    }
    if title_text:
        output["title"] = [{"properties": {
            "show": literal("true"),
            "text": literal(f"'{title_text}'"),
            "fontColor": {"solid": {"color": literal("'#0F172A'")}},
            "background": {"solid": {"color": literal("'#FFFFFF'")}},
            "bold": literal("true"),
        }}]
    return output


def write_visual(report: Path, page: str, key: str, value: dict) -> None:
    visual_id = ident(f"{page}:{key}")
    value["$schema"] = VISUAL_SCHEMA
    value["name"] = visual_id
    write_json(
        report / "definition" / "pages" / page / "visuals" / visual_id / "visual.json",
        value,
    )


def add_textbox(
    report: Path,
    page: str,
    key: str,
    text: str,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    font_size: int = 13,
    bold: bool = False,
    background: str = "#FFFFFF",
    border: str = "#DCE6F2",
    font_color: str = "#0F172A",
    align: str = "left",
    padding: int = 10,
    radius: int = 8,
    z: int = 100,
) -> None:
    write_visual(report, page, key, {
        "position": position(x, y, width, height, z),
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{
                "textRuns": [{"value": text, "textStyle": {
                    "fontFamily": "Segoe UI Semibold" if bold else "Segoe UI",
                    "fontSize": f"{font_size}px", "color": font_color,
                }}],
                "horizontalTextAlignment": align,
            }]}}]},
            "visualContainerObjects": container_style(
                background=background, border=border, shadow=False, padding=padding,
                radius=radius,
            ),
        },
    })


def add_page_chrome(
    report: Path,
    page: str,
    number: int,
    title: str,
    subtitle: str,
    accent: str,
) -> None:
    """Create the shared executive header and navigation rail."""
    add_textbox(
        report, page, "canvas-background", "", 0, 0, 1600, 900,
        background="#F4F7FB", border="#F4F7FB", padding=0, radius=0, z=0,
    )
    add_textbox(
        report, page, "header-background", "", 0, 0, 1600, 100,
        background="#063B5C", border="#063B5C", padding=0, radius=0, z=10,
    )
    add_textbox(
        report, page, "navigation-background", "", 0, 100, 176, 800,
        background="#05334E", border="#05334E", padding=0, radius=0, z=10,
    )
    add_textbox(
        report, page, "page-number", str(number), 16, 14, 66, 66,
        font_size=27, bold=True, background=accent, border=accent,
        font_color="#FFFFFF", align="center", padding=10, radius=33, z=30,
    )
    add_textbox(
        report, page, "title", title, 94, 7, 940, 50,
        font_size=29, bold=True, background="#063B5C", border="#063B5C",
        font_color="#FFFFFF", padding=5, radius=0, z=30,
    )
    add_textbox(
        report, page, "subtitle", subtitle, 94, 57, 940, 30,
        font_size=12, background="#063B5C", border="#063B5C",
        font_color="#B9E6FA", padding=3, radius=0, z=30,
    )
    add_textbox(
        report, page, "brand", "Data Center Intelligence\n2015–2025",
        1300, 17, 276, 62, font_size=11, bold=True,
        background="#063B5C", border="#063B5C", font_color="#E0F2FE",
        align="right", padding=5, radius=0, z=30,
    )
    nav_items = (
        "⌂  Overview", "▣  Infrastructure", "ϟ  Energy", "⚠  Reliability",
        "↗  Predictive", "$  Cost & Carbon", "◎  Impact",
    )
    for index, label in enumerate(nav_items, start=1):
        selected = index == number
        add_textbox(
            report, page, f"navigation-{index}", label, 10, 124 + (index - 1) * 56,
            156, 44, font_size=10, bold=selected,
            background=accent if selected else "#05334E",
            border=accent if selected else "#05334E",
            font_color="#FFFFFF" if selected else "#BBD8E7",
            padding=10, radius=6, z=30,
        )


def add_note(report: Path, page: str, text: str) -> None:
    add_textbox(
        report, page, "note", text, 190, 864, 1386, 26,
        font_size=10, background="#F8FAFC", border="#E2E8F0", z=900,
    )


def add_cards(
    report: Path,
    page: str,
    measure_names: list[str],
    *,
    x: int = 190,
    y: int = 112,
    width: int = 1386,
    accent: str = "#14B8A6",
) -> None:
    gap = 12
    card_width = (width - gap * (len(measure_names) - 1)) // len(measure_names)
    for index, measure_name in enumerate(measure_names):
        write_visual(report, page, f"card-{measure_name}", {
            "position": position(x + index * (card_width + gap), y, card_width, 120, 200 + index),
            "visual": {
                "visualType": "card",
                "query": {"queryState": {"Values": {"projections": [
                    projection(measure("_Measures", measure_name), "_Measures", measure_name)
                ]}}},
                "objects": {
                    "labels": [{"properties": {
                        "color": {"solid": {"color": literal("'#0F172A'")}},
                        "bold": literal("true"),
                    }}],
                    "categoryLabels": [{"properties": {
                        "color": {"solid": {"color": literal("'#475569'")}}
                    }}],
                },
                "visualContainerObjects": container_style(
                    background="#FFFFFF",
                    border=accent if index == 0 else "#DCE6F2",
                    padding=8,
                ),
            },
        })
        add_textbox(
            report, page, f"card-accent-{measure_name}", "",
            x + index * (card_width + gap) + 7, y + 18, 5, 84,
            background=accent, border=accent, padding=0, radius=3,
            z=230 + index,
        )


def add_chart(
    report: Path,
    page: str,
    key: str,
    title_text: str,
    visual_type: str,
    category: tuple[str, str],
    measure_names: list[str],
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    series: tuple[str, str] | None = None,
) -> None:
    state = {
        "Category": {"projections": [projection(column(*category), *category)]},
        "Y": {"projections": [
            projection(measure("_Measures", name), "_Measures", name)
            for name in measure_names
        ]},
    }
    if series:
        state["Series"] = {"projections": [projection(column(*series), *series)]}
    write_visual(report, page, key, {
        "position": position(x, y, width, height, 300 + x + y),
        "visual": {
            "visualType": visual_type,
            "query": {"queryState": state},
            "visualContainerObjects": container_style(title_text=title_text),
        },
    })


def add_donut(
    report: Path,
    page: str,
    key: str,
    title_text: str,
    category: tuple[str, str],
    measure_name: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    state = {
        "Legend": {"projections": [projection(column(*category), *category)]},
        "Values": {"projections": [
            projection(measure("_Measures", measure_name), "_Measures", measure_name)
        ]},
    }
    write_visual(report, page, key, {
        "position": position(x, y, width, height, 400 + x + y),
        "visual": {
            "visualType": "donutChart",
            "query": {"queryState": state},
            "visualContainerObjects": container_style(title_text=title_text),
        },
    })


def add_table(
    report: Path,
    page: str,
    key: str,
    title_text: str,
    fields: list[tuple[str, str, str]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    projections = []
    for field_type, table_name, property_name in fields:
        field = measure(table_name, property_name) if field_type == "measure" else column(table_name, property_name)
        projections.append(projection(field, table_name, property_name))
    write_visual(report, page, key, {
        "position": position(x, y, width, height, 500 + x + y),
        "visual": {
            "visualType": "tableEx",
            "query": {"queryState": {"Values": {"projections": projections}}},
            "objects": {
                "columnHeaders": [{"properties": {
                    "columnAdjustment": literal("'growToFit'"),
                    "autoSizeColumnWidth": literal("true"),
                    "fontColor": {"solid": {"color": literal("'#0F2747'")}},
                    "backColor": {"solid": {"color": literal("'#DBEAFE'")}},
                    "bold": literal("true"),
                }}],
                "values": [{"properties": {
                    "fontColorPrimary": {"solid": {"color": literal("'#1E293B'")}},
                    "backColorPrimary": {"solid": {"color": literal("'#FFFFFF'")}},
                    "fontColorSecondary": {"solid": {"color": literal("'#1E293B'")}},
                    "backColorSecondary": {"solid": {"color": literal("'#F8FAFC'")}},
                }}],
                "grid": [{"properties": {
                    "gridHorizontal": literal("true"),
                    "gridHorizontalColor": {"solid": {"color": literal("'#E2E8F0'")}},
                    "gridVertical": literal("false"),
                    "rowPadding": literal("4D"),
                }}],
            },
            "visualContainerObjects": container_style(title_text=title_text, padding=8),
        },
    })


def add_slicer(
    report: Path,
    page: str,
    key: str,
    field: tuple[str, str],
    x: int,
    *,
    y: int = 16,
) -> None:
    write_visual(report, page, f"slicer-{key}", {
        "position": position(x, y, 150, 46, 150 + x + y),
        "visual": {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [
                projection(column(*field), *field)
            ]}}},
            "visualContainerObjects": container_style(
                background="#FFFFFF", border="#CBD5E1", shadow=False, padding=5
            ),
        },
    })


def build(
    project_root: Path,
    output_root: Path,
    project_name: str = "DataCenter Operations Foundation",
) -> Path:
    contract = json.loads((project_root / "analytics" / "canonical_data_contract.json").read_text(encoding="utf-8"))
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

    refs = [
        "DimDate", "DimFacility", "DimServer", "FactServerMetrics",
        "FactPowerMetrics", "FactNetworkMetrics", "FactIncidents",
        "FactSystemLogs", "FactAlerts", "FactMaintenanceActions",
        "FactAnomalies", "FactServerRisk", "FactFacilityHealth",
        "FactCostCarbon", "FactIncidentImpact", "FactLiveOperationsSnapshot",
        "_Measures",
    ]
    model = "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\nannotation __PBI_TimeIntelligenceEnabled = 0\n\n" + "\n".join(f"ref table {name}" for name in refs) + "\n"
    (semantic / "definition" / "model.tmdl").write_text(model, encoding="utf-8")

    data_root = (project_root / "data" / "processed").resolve()
    for table_name, source_name in TABLES.items():
        query = (project_root / "powerbi" / "foundation" / "PowerQuery" / f"{table_name}.pq").read_text(encoding="utf-8")
        content = table_tmdl(table_name, source_name, contract["tables"][source_name], query, data_root)
        (semantic / "definition" / "tables" / f"{table_name}.tmdl").write_text(content, encoding="utf-8")
    for table_name, columns in SNAPSHOT_TABLES.items():
        source_file = {
            "FactCostCarbon": "powerbi_cost_carbon_snapshot.csv",
            "FactIncidentImpact": "powerbi_incident_impact_snapshot.csv",
            "FactLiveOperationsSnapshot": "powerbi_live_operations_snapshot.csv",
        }[table_name]
        if not (data_root / source_file).exists():
            raise FileNotFoundError(
                f"Missing {source_file}; run python -m scripts.export_powerbi_snapshots first"
            )
        query = (
            project_root / "powerbi" / "foundation" / "PowerQuery" / f"{table_name}.pq"
        ).read_text(encoding="utf-8")
        definition = {
            "columns": {
                name: {"type": data_type, "nullable": True}
                for name, data_type in columns.items()
            }
        }
        content = table_tmdl(table_name, source_file, definition, query, data_root)
        (semantic / "definition" / "tables" / f"{table_name}.tmdl").write_text(
            content, encoding="utf-8"
        )
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

relationship rel_facility_logs
\tfromColumn: FactSystemLogs.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_server_logs
\tisActive: false
\tfromColumn: FactSystemLogs.server_id
\ttoColumn: DimServer.server_id

relationship rel_date_logs
\tfromColumn: FactSystemLogs.log_date
\ttoColumn: DimDate.Date

relationship rel_facility_alerts
\tfromColumn: FactAlerts.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_server_alerts
\tisActive: false
\tfromColumn: FactAlerts.server_id
\ttoColumn: DimServer.server_id

relationship rel_date_alerts
\tfromColumn: FactAlerts.alert_date
\ttoColumn: DimDate.Date

relationship rel_facility_actions
\tfromColumn: FactMaintenanceActions.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_server_actions
\tisActive: false
\tfromColumn: FactMaintenanceActions.server_id
\ttoColumn: DimServer.server_id

relationship rel_date_actions
\tfromColumn: FactMaintenanceActions.action_date
\ttoColumn: DimDate.Date

relationship rel_facility_anomalies
\tfromColumn: FactAnomalies.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_date_anomalies
\tfromColumn: FactAnomalies.timestamp
\ttoColumn: DimDate.Date

relationship rel_server_risk
\tfromColumn: FactServerRisk.server_id
\ttoColumn: DimServer.server_id

relationship rel_date_risk
\tfromColumn: FactServerRisk.score_date
\ttoColumn: DimDate.Date

relationship rel_facility_health
\tfromColumn: FactFacilityHealth.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_date_health
\tfromColumn: FactFacilityHealth.score_date
\ttoColumn: DimDate.Date

relationship rel_facility_cost_carbon
\tfromColumn: FactCostCarbon.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_date_cost_carbon
\tfromColumn: FactCostCarbon.snapshot_date
\ttoColumn: DimDate.Date

relationship rel_facility_incident_impact
\tfromColumn: FactIncidentImpact.facility_id
\ttoColumn: DimFacility.facility_id

relationship rel_date_incident_impact
\tfromColumn: FactIncidentImpact.incident_date
\ttoColumn: DimDate.Date

relationship rel_facility_live_snapshot
\tfromColumn: FactLiveOperationsSnapshot.facility_id
\ttoColumn: DimFacility.facility_id
"""
    (semantic / "definition" / "relationships.tmdl").write_text(relationships, encoding="utf-8")

    write_json(report / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{project_name}.SemanticModel"}},
    })
    write_json(report / "definition" / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    theme_name = "DataCenterExecutive-20260904.json"
    theme = json.loads(
        (project_root / "powerbi" / "theme" / "DataCenterExecutive.json").read_text(
            encoding="utf-8"
        )
    )
    theme["name"] = theme_name
    write_json(report / "StaticResources" / "RegisteredResources" / theme_name, theme)
    report_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "customTheme": {
                "name": theme_name,
                "reportVersionAtImport": {
                    "visual": "2.9.0", "report": "3.3.0", "page": "2.1.0"
                },
                "type": "RegisteredResources",
            }
        },
        "resourcePackages": [{
            "name": "RegisteredResources", "type": "RegisteredResources",
            "items": [{"name": theme_name, "path": theme_name, "type": "CustomTheme"}],
        }],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultFilterActionIsDataFilter": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "allowInlineExploration": True,
            "useEnhancedTooltips": True,
        },
    }
    write_json(report / "definition" / "report.json", report_json)
    # PBIR page names are internal opaque identifiers, not display-name slugs.
    page_defs = [
        ("dce0f001202608140001", "Executive Operations Overview"),
        ("dce0f001202608140002", "Infrastructure Performance"),
        ("dce0f001202608140003", "Energy & Reliability"),
        ("dce0f001202608140004", "Reliability & Incident Intelligence"),
        ("dce0f001202608140005", "Predictive Operations"),
        ("dce0f001202608140006", "Cost & Sustainability"),
        ("dce0f001202608140007", "Reliability Impact"),
    ]
    pages = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [name for name, _ in page_defs],
        "activePageName": page_defs[0][0],
    }
    write_json(report / "definition" / "pages" / "pages.json", pages)
    for name, display in page_defs:
        folder = report / "definition" / "pages" / name
        folder.mkdir()
        page = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": 900, "width": 1600,
        }
        write_json(folder / "page.json", page)

    p1, p2, p3, p4, p5, p6, p7 = [name for name, _ in page_defs]
    page_settings = (
        (p1, 1, page_defs[0][1], "Key insights. Stronger operations. A more resilient tomorrow.", "#14B8A6", ("DimDate", "Year")),
        (p2, 2, page_defs[1][1], "Monitor. Analyze. Optimize.", "#2388E8", ("DimServer", "server_type")),
        (p3, 3, page_defs[2][1], "Efficient energy. Reliable operations.", "#46A51B", ("DimDate", "Year")),
        (p4, 4, page_defs[3][1], "Detect. Investigate. Prevent.", "#F2A900", ("FactIncidents", "severity")),
        (p5, 5, page_defs[4][1], "From evidence to what comes next.", "#0EA47A", ("FactServerRisk", "risk_level")),
        (p6, 6, page_defs[5][1], "Lower cost. Greener operations.", "#78B800", ("DimDate", "Year")),
        (p7, 7, page_defs[6][1], "From incidents to insight. From insight to resilience.", "#2388E8", ("FactIncidentImpact", "severity")),
    )
    for page, number, title_text, subtitle, accent, second_slicer in page_settings:
        add_page_chrome(report, page, number, title_text, subtitle, accent)
        add_slicer(report, page, "facility", ("DimFacility", "facility_name"), 12, y=690)
        add_slicer(report, page, "context", second_slicer, 12, y=752)

    add_cards(report, p1, [
        "Server Count", "Operational Availability", "Incident Count",
        "Average PUE", "Modeled Energy Cost", "Live Facility Health Score",
    ], accent="#14B8A6")
    add_chart(report, p1, "pue-trend", "PUE trend | monthly, 2015–2025", "lineChart",
              ("DimDate", "Month Year"), ["Average PUE"], 190, 250, 680, 270)
    add_chart(report, p1, "downtime-facility", "Downtime by facility | minutes",
              "clusteredBarChart", ("DimFacility", "facility_name"),
              ["Total Downtime"], 890, 250, 686, 270)
    add_table(report, p1, "facility-scorecard", "Facility operations scorecard", [
        ("column", "DimFacility", "facility_name"), ("measure", "_Measures", "Average PUE"),
        ("measure", "_Measures", "Operational Availability"), ("measure", "_Measures", "Incident Count"),
        ("measure", "_Measures", "Modeled Energy Cost"), ("measure", "_Measures", "Live Facility Health Score"),
    ], 190, 535, 880, 310)
    add_chart(report, p1, "live-health", "Latest simulated facility health score", "clusteredBarChart",
              ("DimFacility", "facility_name"), ["Live Facility Health Score"], 1088, 535, 488, 310)
    add_note(report, p1, "Historical period: 2015–2025 synthetic data. Live health uses the latest bounded simulation snapshot.")

    add_cards(report, p2, [
        "Server Count", "Average CPU Utilization", "Average Memory Utilization",
        "Average Network Latency", "Average Throughput",
    ], accent="#2388E8")
    add_chart(report, p2, "utilization-trend", "Resource utilization trend | percent", "lineChart",
              ("DimDate", "Month Year"), ["Average CPU Utilization", "Average Memory Utilization", "Average Disk Utilization"],
              190, 250, 680, 270)
    add_chart(report, p2, "utilization-facility", "CPU and memory utilization by facility | percent",
              "clusteredColumnChart", ("DimFacility", "facility_name"),
              ["Average CPU Utilization", "Average Memory Utilization"], 890, 250, 686, 270)
    add_table(report, p2, "server-detail", "Server performance detail", [
        ("column", "DimServer", "server_id"), ("column", "DimServer", "server_type"),
        ("column", "DimServer", "status"), ("measure", "_Measures", "Average CPU Utilization"),
        ("measure", "_Measures", "Average Memory Utilization"), ("measure", "_Measures", "Average Disk Utilization"),
    ], 190, 535, 880, 310)
    add_donut(report, p2, "server-status", "Server status distribution", ("DimServer", "status"),
              "Server Count", 1088, 535, 488, 310)
    add_note(report, p2, "Daily utilization is filtered through the conformed facility, server and date dimensions.")

    add_cards(report, p3, [
        "Average PUE", "Total Power Draw", "Total Cooling Power",
        "Modeled Energy Cost", "Operational Availability",
    ], accent="#46A51B")
    add_chart(report, p3, "pue-monthly", "PUE trend | monthly, 2015–2025", "lineChart",
              ("DimDate", "Month Year"), ["Average PUE"], 190, 250, 680, 270)
    add_chart(report, p3, "power-facility", "IT load and cooling power by facility | kW",
              "stackedColumnChart", ("DimFacility", "facility_name"),
              ["Total IT Load", "Total Cooling Power"], 890, 250, 686, 270)
    add_chart(report, p3, "cost-trend", "Modeled energy cost trend | USD", "lineChart",
              ("DimDate", "Month Year"), ["Modeled Energy Cost"], 190, 535, 520, 310)
    add_donut(report, p3, "cost-share", "Modeled energy cost share by facility",
              ("DimFacility", "facility_name"), "Modeled Energy Cost", 728, 535, 350, 310)
    add_table(report, p3, "energy-reliability", "Facility energy and reliability", [
        ("column", "DimFacility", "facility_name"), ("measure", "_Measures", "Average PUE"),
        ("measure", "_Measures", "Total Power Draw"), ("measure", "_Measures", "Total Cooling Power"),
        ("measure", "_Measures", "Operational Availability"),
    ], 1096, 535, 480, 310)
    add_note(report, p3, "Power values are daily observations. Cost and carbon values use governed synthetic assumptions.")

    add_cards(report, p4, [
        "Incident Count", "MTTR Minutes", "Operational Availability",
        "Alert Count", "Anomaly Count", "Critical Alert Count",
    ], accent="#F2A900")
    add_chart(report, p4, "incident-trend", "Incident trend | monthly count", "lineChart",
              ("DimDate", "Month Year"), ["Incident Count"], 190, 250, 680, 270)
    add_donut(report, p4, "incident-root-cause", "Incidents by recorded root cause",
              ("FactIncidents", "root_cause"), "Incident Count", 890, 250, 686, 270)
    add_table(report, p4, "incident-detail", "Recent incident evidence", [
        ("column", "FactIncidents", "incident_date"), ("column", "DimFacility", "facility_name"),
        ("column", "FactIncidents", "server_id"), ("column", "FactIncidents", "severity"),
        ("column", "FactIncidents", "root_cause"), ("column", "FactIncidents", "downtime_minutes"),
    ], 190, 535, 880, 310)
    add_chart(report, p4, "mttr-trend", "Incident resolution time | average minutes", "lineChart",
              ("DimDate", "Year"), ["MTTR Minutes"], 1088, 535, 488, 310)
    add_note(report, p4, "Root cause is the recorded synthetic incident label; the dashboard does not infer causality.")

    add_cards(report, p5, [
        "Average Server Risk Score", "High Risk Server Count", "Average Facility Health Score",
        "Live Facility Health Score", "Live Data Completeness",
    ], accent="#0EA47A")
    add_chart(report, p5, "risk-distribution", "Server risk observations by level", "clusteredColumnChart",
              ("FactServerRisk", "risk_level"), ["Server Risk Observation Count"], 190, 250, 680, 270)
    add_chart(report, p5, "facility-health", "Average facility health score", "clusteredBarChart",
              ("DimFacility", "facility_name"), ["Average Facility Health Score"], 890, 250, 686, 270)
    add_table(report, p5, "risk-detail", "Highest-risk server evidence", [
        ("column", "FactServerRisk", "server_id"), ("column", "FactServerRisk", "score_date"),
        ("column", "FactServerRisk", "risk_score"), ("column", "FactServerRisk", "risk_level"),
        ("column", "FactServerRisk", "primary_signal"), ("column", "FactServerRisk", "recommendation"),
    ], 190, 535, 880, 310)
    add_chart(report, p5, "live-facility-health", "Latest simulated health by facility", "clusteredBarChart",
              ("DimFacility", "facility_name"), ["Live Facility Health Score"], 1088, 535, 488, 310)
    add_note(report, p5, "Risk and health scores are screening signals, not guaranteed failures. Review evidence before action.")

    add_cards(report, p6, [
        "Modeled Energy Cost", "Modeled Cooling Cost", "Modeled Carbon",
        "Average Energy Price", "Average Efficiency Opportunity Score",
    ], accent="#78B800")
    add_chart(report, p6, "cost-trend", "Annual modeled energy cost | USD", "clusteredColumnChart",
              ("DimDate", "Year"), ["Modeled Energy Cost"], 190, 250, 680, 270)
    add_chart(report, p6, "carbon-trend", "Annual modeled carbon | tonnes CO₂e", "clusteredColumnChart",
              ("DimDate", "Year"), ["Modeled Carbon"], 890, 250, 686, 270)
    add_donut(report, p6, "cost-facility", "Modeled energy cost share by facility",
              ("DimFacility", "facility_name"), "Modeled Energy Cost", 190, 535, 410, 310)
    add_chart(report, p6, "opportunity-facility", "Efficiency opportunity score by facility", "clusteredBarChart",
              ("DimFacility", "facility_name"), ["Average Efficiency Opportunity Score"], 618, 535, 460, 310)
    add_table(report, p6, "sustainability-detail", "Governed sustainability snapshot", [
        ("column", "FactCostCarbon", "snapshot_date"), ("column", "DimFacility", "facility_name"),
        ("measure", "_Measures", "Modeled Energy Cost"), ("measure", "_Measures", "Modeled Cooling Cost"),
        ("measure", "_Measures", "Modeled Carbon"), ("measure", "_Measures", "Average Energy Price"),
    ], 1096, 535, 480, 310)
    add_note(report, p6, "Modeled values use synthetic price and location-based carbon assumptions; they are not invoices or audited emissions.")

    add_cards(report, p7, [
        "Incident Impact Count", "Modeled Downtime Cost Exposure", "Average Incident PUE Change",
        "Average Incident Latency Change", "Total Downtime",
    ], accent="#2388E8")
    add_chart(report, p7, "impact-trend", "Modeled downtime exposure trend | USD", "lineChart",
              ("DimDate", "Month Year"), ["Modeled Downtime Cost Exposure"], 190, 250, 680, 270)
    add_chart(report, p7, "impact-root-cause", "Modeled exposure by recorded root cause | USD", "clusteredBarChart",
              ("FactIncidentImpact", "root_cause"), ["Modeled Downtime Cost Exposure"], 890, 250, 686, 270)
    add_table(report, p7, "impact-detail", "Highest-impact incident evidence", [
        ("column", "FactIncidentImpact", "incident_date"), ("column", "DimFacility", "facility_name"),
        ("column", "FactIncidentImpact", "severity"), ("column", "FactIncidentImpact", "root_cause"),
        ("column", "FactIncidentImpact", "downtime_minutes"),
        ("column", "FactIncidentImpact", "modeled_downtime_cost_exposure_usd"),
    ], 190, 535, 880, 310)
    add_chart(report, p7, "change-by-root-cause", "Average incident change by root cause | percent", "clusteredBarChart",
              ("FactIncidentImpact", "root_cause"), ["Average Incident PUE Change", "Average Incident Latency Change"],
              1088, 535, 488, 310)
    add_note(report, p7, "Before/after changes are descriptive seven-day associations; they do not establish causal effects.")
    return output_root / f"{project_name}.pbip"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Step 7 PBIP foundation.")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("powerbi/PBI"))
    parser.add_argument(
        "--project-name",
        default="DataCenter Operations Foundation",
        help="Power BI project/report/model name.",
    )
    args = parser.parse_args()
    path = build(args.project_root.resolve(), args.output.resolve(), args.project_name)
    print(path)


if __name__ == "__main__":
    main()

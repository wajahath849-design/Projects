"""Build the editable seven-page Power BI report and its small reporting marts.

Run after ``run_pipeline.py``. Power BI Desktop creates the PBIP shell; this
script authors PBIR pages and embeds the compact synthetic reporting snapshot
in the semantic model so the committed PBIP has no machine-specific paths.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import shutil
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
REPORT = PBI / "Financial Project Performance.Report"
MODEL = PBI / "Financial Project Performance.SemanticModel"
DEFINITION = REPORT / "definition"
PAGES = DEFINITION / "pages"
TABLES = MODEL / "definition" / "tables"
CURATED = ROOT / "data" / "curated"
REFRESH = json.loads((ROOT / "reports" / "refresh_report.json").read_text())
AS_OF = date.fromisoformat(REFRESH["as_of_date"])

SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"

NAVY = "#17324D"
TEAL = "#167D8D"
MUTED = "#627688"
PAPER = "#F5F7FA"
WHITE = "#FFFFFF"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ident(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:20]


def lineage(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "financial-project-performance-bi/" + key))


def make_marts() -> dict[str, list[tuple[str, str]]]:
    costs = read_csv(CURATED / "FactActualCost.csv")
    revenue = read_csv(CURATED / "FactRevenue.csv")
    categories = {r["category_id"]: r for r in read_csv(CURATED / "DimCostCategory.csv")}
    departments = {r["department_id"]: r["department_name"] for r in read_csv(CURATED / "DimDepartment.csv")}

    monthly = defaultdict(lambda: {"actual_cost_usd": 0.0, "recognized_revenue_usd": 0.0})
    driver = defaultdict(lambda: {"actual_cost_usd": 0.0, "transaction_count": 0})
    for row in costs:
        month = row["transaction_date"][:7]
        amount = float(row["amount"])
        monthly[month]["actual_cost_usd"] += amount
        cat = categories[row["category_id"]]
        key = (departments[row["department_id"]], cat["category_name"], cat["cost_group"])
        driver[key]["actual_cost_usd"] += amount
        driver[key]["transaction_count"] += 1
    for row in revenue:
        monthly[row["recognition_date"][:7]]["recognized_revenue_usd"] += float(row["recognized_revenue_usd"])

    monthly_rows = []
    for month, values in sorted(monthly.items()):
        if month > AS_OF.isoformat()[:7]:
            continue
        monthly_rows.append({
            "month": month,
            "actual_cost_usd": round(values["actual_cost_usd"], 2),
            "recognized_revenue_usd": round(values["recognized_revenue_usd"], 2),
            "gross_profit_usd": round(values["recognized_revenue_usd"] - values["actual_cost_usd"], 2),
        })
    write_csv(CURATED / "MonthlyFinance.csv", list(monthly_rows[0]), monthly_rows)

    driver_rows = [
        {"department_name": dep, "category_name": cat, "cost_group": grp,
         "actual_cost_usd": round(values["actual_cost_usd"], 2),
         "transaction_count": values["transaction_count"]}
        for (dep, cat, grp), values in sorted(driver.items())
    ]
    write_csv(CURATED / "ExpenseDrivers.csv", list(driver_rows[0]), driver_rows)

    future = defaultdict(lambda: defaultdict(float))
    for row in read_csv(CURATED / "FactForecast.csv"):
        if row["is_latest_valid"].lower() != "true" or row["forecast_month"][:7] <= AS_OF.isoformat()[:7]:
            continue
        future[row["forecast_month"][:7]][row["scenario"]] += float(row["forecast_cost_usd"])
    forecast_rows = [
        {"month": month, "base_cost_usd": round(v["base"], 2),
         "optimistic_cost_usd": round(v["optimistic"], 2),
         "downside_cost_usd": round(v["downside"], 2)}
        for month, v in sorted(future.items())
    ]
    write_csv(CURATED / "ForecastMonthly.csv", list(forecast_rows[0]), forecast_rows)

    reasons = defaultdict(int)
    for row in read_csv(ROOT / "reports" / "data_quality_exceptions.csv"):
        reasons[(row["source"], row["reason"])] += 1
    issue_rows = [{"source": s, "reason": r.replace("_", " ").capitalize(), "rejected_rows": n}
                  for (s, r), n in sorted(reasons.items())]
    write_csv(CURATED / "AuditIssues.csv", list(issue_rows[0]), issue_rows)

    source_rows = [{"source": r["source"], "rows": int(r["rows"]), "modified_utc": r["modified_utc"][:10]}
                   for r in read_csv(ROOT / "reports" / "source_manifest.csv")]
    write_csv(CURATED / "AuditSources.csv", list(source_rows[0]), source_rows)

    audit = [{
        "rejected_rows": REFRESH["rejected_rows"],
        "source_rows": sum(REFRESH["source_rows"].values()),
        "reconciliation_delta_usd": round(sum(abs(v) for k, v in REFRESH["reconciliation"].items() if k.endswith("_usd")), 2),
        "holdout_mae_usd": REFRESH["forecast_holdout_mae_usd"],
    }]
    write_csv(CURATED / "AuditSummary.csv", list(audit[0]), audit)

    return {
        "MonthlyFinance": [("month", "string"), ("actual_cost_usd", "double"),
                           ("recognized_revenue_usd", "double"), ("gross_profit_usd", "double")],
        "ExpenseDrivers": [("department_name", "string"), ("category_name", "string"),
                           ("cost_group", "string"), ("actual_cost_usd", "double"),
                           ("transaction_count", "int64")],
        "ForecastMonthly": [("month", "string"), ("base_cost_usd", "double"),
                            ("optimistic_cost_usd", "double"), ("downside_cost_usd", "double")],
        "AuditIssues": [("source", "string"), ("reason", "string"), ("rejected_rows", "int64")],
        "AuditSources": [("source", "string"), ("rows", "int64"), ("modified_utc", "string")],
        "AuditSummary": [("rejected_rows", "int64"), ("source_rows", "int64"),
                         ("reconciliation_delta_usd", "double"), ("holdout_mae_usd", "double")],
    }


def embedded_csv(path: Path) -> str:
    """Return a portable Power Query binary expression for a small CSV."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'Binary.FromText("{encoded}", BinaryEncoding.Base64)'


def embed_project_metrics() -> None:
    """Keep Desktop-authored column metadata while updating its source."""
    path = TABLES / "ProjectMetrics.tmdl"
    lines = path.read_text(encoding="utf-8").splitlines()
    source_lines = [i for i, line in enumerate(lines) if "Source = Csv.Document(" in line]
    if len(source_lines) != 1:
        raise ValueError("Expected one ProjectMetrics CSV source in the semantic model")
    i = source_lines[0]
    indent = lines[i].split("Source =", 1)[0]
    columns = len(read_csv(CURATED / "ProjectMetrics.csv")[0])
    lines[i] = (f'{indent}Source = Csv.Document({embedded_csv(CURATED / "ProjectMetrics.csv")},'
                f'[Delimiter=",", Columns={columns}, Encoding=65001, QuoteStyle=QuoteStyle.None]),')
    while lines and not lines[-1].strip():
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tmdl_for_csv(table: str, columns: list[tuple[str, str]]) -> str:
    lines = [f"table {table}", f"\tlineageTag: {lineage(table)}", ""]
    for name, kind in columns:
        lines += [f"\tcolumn {name}", f"\t\tdataType: {kind}", f"\t\tlineageTag: {lineage(table + '/' + name)}",
                  f"\t\tsummarizeBy: {'none' if kind == 'string' else 'sum'}", f"\t\tsourceColumn: {name}"]
        if name.endswith("_usd"):
            lines.append("\t\tformatString: $#,0.00;($#,0.00)")
        lines += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
    types = ", ".join(f'{{"{name}", {"type text" if kind == "string" else "Int64.Type" if kind == "int64" else "type number"}}}'
                      for name, kind in columns)
    lines += [f"\tpartition {table} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
              f'\t\t\t\t    Source = Csv.Document({embedded_csv(CURATED / (table + ".csv"))},[Delimiter=",", Columns={len(columns)}, Encoding=65001, QuoteStyle=QuoteStyle.None]),',
              '\t\t\t\t    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
              f'\t\t\t\t    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{{{types}}})',
              "\t\t\t\tin", '\t\t\t\t    #"Changed Type"', "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(lines)


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def color(value: str) -> dict:
    return {"solid": {"color": literal(f"'{value}'")}}


def projection(table: str, field: str, label: str | None = None, aggregate: bool = False) -> dict:
    col = {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": field}}
    expr = {"Aggregation": {"Expression": col, "Function": 0}} if aggregate else col
    result = {"field": expr, "queryRef": f"Sum({table}.{field})" if aggregate else f"{table}.{field}",
              "nativeQueryRef": f"Sum of {field}" if aggregate else field}
    if label:
        result["displayName"] = label
    if not aggregate:
        result["active"] = True
    return result


def title_format(title: str) -> dict:
    return {"title": [{"properties": {
        "show": literal("true"), "text": literal("'" + title.replace("'", "''") + "'"),
        "fontColor": color(NAVY), "fontSize": literal("13D"),
        "fontFamily": literal("'Segoe UI Semibold'"), "alignment": literal("'left'")}}],
        "background": [{"properties": {"show": literal("true"), "color": color(WHITE), "transparency": literal("0D")}}],
        "border": [{"properties": {"show": literal("false")}}],
        "padding": [{"properties": {"top": literal("8D"), "bottom": literal("8D"),
                                     "left": literal("10D"), "right": literal("10D")}}]}


def base_visual(page: str, key: str, kind: str, x: int, y: int, w: int, h: int, z: int) -> dict:
    name = ident(page + "/" + key)
    return {"$schema": SCHEMA_VISUAL, "name": name,
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
            "visual": {"visualType": kind, "drillFilterOtherVisuals": True}}


def text_visual(page: str, key: str, value: str, x: int, y: int, w: int, h: int,
                size: int = 11, ink: str = NAVY, bold: bool = False, z: int = 0) -> dict:
    item = base_visual(page, key, "textbox", x, y, w, h, z)
    item["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [{
        "textRuns": [{"value": value, "textStyle": {"fontFamily": "Segoe UI Semibold" if bold else "Segoe UI",
                                                     "fontSize": f"{size}pt", "color": ink}}],
        "horizontalTextAlignment": "left"}]}}]}
    item["visual"]["visualContainerObjects"] = {
        "background": [{"properties": {"show": literal("false")}}],
        "border": [{"properties": {"show": literal("false")}}],
        "padding": [{"properties": {"top": literal("0D"), "bottom": literal("0D"),
                                     "left": literal("0D"), "right": literal("0D")}}]}
    return item


def card(page: str, key: str, label: str, table: str, field: str, x: int, y: int, w: int,
         h: int = 115, z: int = 10) -> dict:
    item = base_visual(page, key, "cardVisual", x, y, w, h, z)
    item["visual"]["query"] = {"queryState": {"Data": {"projections": [projection(table, field, label, True)]}}}
    item["visual"]["visualContainerObjects"] = title_format(label)
    return item


def chart(page: str, key: str, title: str, kind: str, category: tuple[str, str, str],
          values: list[tuple[str, str, str]], x: int, y: int, w: int, h: int, z: int = 20) -> dict:
    item = base_visual(page, key, kind, x, y, w, h, z)
    table, field, label = category
    item["visual"]["query"] = {"queryState": {
        "Category": {"projections": [projection(table, field, label)]},
        "Y": {"projections": [projection(t, f, l, True) for t, f, l in values]}}}
    item["visual"]["visualContainerObjects"] = title_format(title)
    return item


def table(page: str, key: str, title: str, columns: list[tuple[str, str, str, bool]],
          x: int, y: int, w: int, h: int, z: int = 30) -> dict:
    item = base_visual(page, key, "tableEx", x, y, w, h, z)
    fields = [projection(t, f, l, a) for t, f, l, a in columns]
    # In a table visual, active marks a drill level and can suppress grid rows.
    for field in fields:
        field.pop("active", None)
    item["visual"]["query"] = {"queryState": {"Values": {"projections": fields}}}
    item["visual"]["visualContainerObjects"] = title_format(title)
    return item


def slicer(page: str, key: str, title: str, column: tuple[str, str, str],
           x: int, y: int, w: int, h: int) -> dict:
    item = base_visual(page, key, "slicer", x, y, w, h, 18)
    t, f, l = column
    item["visual"]["query"] = {"queryState": {"Values": {"projections": [projection(t, f, l)]}}}
    item["visual"]["visualContainerObjects"] = title_format(title)
    return item


def build_pages() -> None:
    first_id = "bf8f9e2b89e66059369a"
    specs = [
        (first_id, "Executive overview", "The portfolio position, with exceptions kept in view."),
        (ident("page/budget"), "Budget vs actual", "See where approved funding is being used and where costs have moved ahead."),
        (ident("page/profit"), "Profitability", "Revenue and cost together show which projects create or dilute margin."),
        (ident("page/expense"), "Expense analysis", "Follow cost by category, department and month; corrections remain signed."),
        (ident("page/forecast"), "Forecast & risk", "Compare the remaining-cost scenarios and the projects most exposed."),
        (ident("page/detail"), "Project detail", "Choose a project and inspect its budget, delivery and financial result."),
        (ident("page/audit"), "Data quality & audit", "Trace the refresh, rejected rows and source volumes behind the report."),
    ]
    order = []
    for number, (pid, display, subtitle) in enumerate(specs, 1):
        order.append(pid)
        folder = PAGES / pid
        folder.mkdir(parents=True, exist_ok=True)
        visual_dir = folder / "visuals"
        if visual_dir.exists():
            assert visual_dir.resolve().is_relative_to(PAGES.resolve())
            shutil.rmtree(visual_dir)
        visual_dir.mkdir()
        page = {"$schema": SCHEMA_PAGE, "name": pid, "displayName": display,
                "displayOption": "FitToPage", "height": 720, "width": 1280,
                "objects": {"background": [{"properties": {"color": color(PAPER),
                                                           "transparency": literal("0D")}}]}}
        write_json(folder / "page.json", page)

        visuals = [
            text_visual(pid, "heading", display, 52, 23, 1030, 50, 26, NAVY, True, 0),
            text_visual(pid, "subtitle", subtitle, 52, 76, 1080, 29, 11, MUTED, False, 1),
            text_visual(pid, "footer", f"As of {AS_OF:%d %b %Y}  ·  USD  ·  Synthetic demonstration data", 52, 686, 950, 23, 9, MUTED, False, 90),
            text_visual(pid, "page-number", f"{number:02d} / 07", 1145, 686, 90, 23, 9, MUTED, False, 91),
        ]
        def cards(items: list[tuple[str, str, str]]) -> None:
            gap = 16
            width = (1176 - (len(items) - 1) * gap) // len(items)
            for idx, (label, t, f) in enumerate(items):
                visuals.append(card(pid, f"card-{idx}", label, t, f, 52 + idx * (width + gap), 132, width))

        if number == 1:
            cards([("Approved budget", "ProjectMetrics", "approved_budget_usd"),
                   ("Actual cost", "ProjectMetrics", "actual_cost_usd"),
                   ("Recognized revenue", "ProjectMetrics", "recognized_revenue_usd"),
                   ("Gross profit", "ProjectMetrics", "gross_profit_usd")])
            visuals += [
                chart(pid, "status-budget", "Budget and cost by delivery status", "clusteredColumnChart",
                      ("ProjectMetrics", "status", "Status"),
                      [("ProjectMetrics", "approved_budget_usd", "Approved budget"),
                       ("ProjectMetrics", "actual_cost_usd", "Actual cost")], 52, 278, 565, 225),
                chart(pid, "status-profit", "Gross profit by delivery status", "clusteredBarChart",
                      ("ProjectMetrics", "status", "Status"),
                      [("ProjectMetrics", "gross_profit_usd", "Gross profit")], 635, 278, 593, 225),
                table(pid, "attention", "Project financial position",
                      [("ProjectMetrics", "project_name", "Project", False),
                       ("ProjectMetrics", "financial_health", "Health", False),
                       ("ProjectMetrics", "budget_variance_usd", "Budget variance", True),
                       ("ProjectMetrics", "forecast_overrun_usd", "Forecast overrun", True)],
                      52, 519, 1176, 150),
            ]
        elif number == 2:
            cards([("Approved budget", "ProjectMetrics", "approved_budget_usd"),
                   ("Actual cost", "ProjectMetrics", "actual_cost_usd"),
                   ("Budget remaining", "ProjectMetrics", "budget_variance_usd"),
                   ("Forecast overrun", "ProjectMetrics", "forecast_overrun_usd")])
            visuals += [
                chart(pid, "project-budget", "Project budgets against spend", "clusteredBarChart",
                      ("ProjectMetrics", "project_name", "Project"),
                      [("ProjectMetrics", "approved_budget_usd", "Approved budget"),
                       ("ProjectMetrics", "actual_cost_usd", "Actual cost")], 52, 277, 575, 390),
                table(pid, "budget-register", "Budget register",
                      [("ProjectMetrics", "project_name", "Project", False),
                       ("ProjectMetrics", "status", "Status", False),
                       ("ProjectMetrics", "approved_budget_usd", "Approved", True),
                       ("ProjectMetrics", "actual_cost_usd", "Actual", True),
                       ("ProjectMetrics", "budget_variance_usd", "Remaining", True)],
                      645, 277, 583, 390),
            ]
        elif number == 3:
            cards([("Recognized revenue", "ProjectMetrics", "recognized_revenue_usd"),
                   ("Actual cost", "ProjectMetrics", "actual_cost_usd"),
                   ("Gross profit", "ProjectMetrics", "gross_profit_usd")])
            visuals += [
                chart(pid, "revenue-cost-status", "Revenue and cost by status", "clusteredColumnChart",
                      ("ProjectMetrics", "status", "Status"),
                      [("ProjectMetrics", "recognized_revenue_usd", "Revenue"),
                       ("ProjectMetrics", "actual_cost_usd", "Actual cost")], 52, 278, 565, 225),
                chart(pid, "project-profit", "Gross profit by project", "clusteredBarChart",
                      ("ProjectMetrics", "project_name", "Project"),
                      [("ProjectMetrics", "gross_profit_usd", "Gross profit")], 635, 278, 593, 225),
                table(pid, "profit-register", "Project profit and margin",
                      [("ProjectMetrics", "project_name", "Project", False),
                       ("ProjectMetrics", "recognized_revenue_usd", "Revenue", True),
                       ("ProjectMetrics", "actual_cost_usd", "Cost", True),
                       ("ProjectMetrics", "gross_profit_usd", "Profit", True),
                       ("ProjectMetrics", "gross_margin_pct", "Margin", False)],
                      52, 519, 1176, 150),
            ]
        elif number == 4:
            cards([("Total actual cost", "ProjectMetrics", "actual_cost_usd"),
                   ("Cost transactions", "ExpenseDrivers", "transaction_count"),
                   ("Recognized revenue", "ProjectMetrics", "recognized_revenue_usd")])
            visuals += [
                chart(pid, "category-cost", "Cost by category", "clusteredBarChart",
                      ("ExpenseDrivers", "category_name", "Category"),
                      [("ExpenseDrivers", "actual_cost_usd", "Actual cost")], 52, 278, 565, 221),
                chart(pid, "department-cost", "Cost by department", "clusteredBarChart",
                      ("ExpenseDrivers", "department_name", "Department"),
                      [("ExpenseDrivers", "actual_cost_usd", "Actual cost")], 635, 278, 593, 221),
                chart(pid, "monthly-cost", "Monthly actual cost", "lineChart",
                      ("MonthlyFinance", "month", "Month"),
                      [("MonthlyFinance", "actual_cost_usd", "Actual cost")], 52, 519, 1176, 150),
            ]
        elif number == 5:
            cards([("Estimate to complete", "ProjectMetrics", "estimate_to_complete_usd"),
                   ("Estimate at completion", "ProjectMetrics", "estimate_at_completion_usd"),
                   ("Forecast overrun", "ProjectMetrics", "forecast_overrun_usd"),
                   ("Approved budget", "ProjectMetrics", "approved_budget_usd")])
            visuals += [
                chart(pid, "forecast-scenarios", "Remaining cost scenarios by month", "lineChart",
                      ("ForecastMonthly", "month", "Month"),
                      [("ForecastMonthly", "base_cost_usd", "Base"),
                       ("ForecastMonthly", "optimistic_cost_usd", "Optimistic"),
                       ("ForecastMonthly", "downside_cost_usd", "Downside")], 52, 278, 1176, 210),
                chart(pid, "overrun-project", "Projects with forecast cost exposure", "clusteredBarChart",
                      ("ProjectMetrics", "project_name", "Project"),
                      [("ProjectMetrics", "forecast_overrun_usd", "Forecast overrun")], 52, 508, 1176, 161),
            ]
        elif number == 6:
            visuals += [
                slicer(pid, "project-selector", "Select project", ("ProjectMetrics", "project_name", "Project"),
                       52, 132, 330, 116),
                card(pid, "budget", "Approved budget", "ProjectMetrics", "approved_budget_usd", 401, 132, 260),
                card(pid, "cost", "Actual cost", "ProjectMetrics", "actual_cost_usd", 680, 132, 260),
                card(pid, "profit", "Gross profit", "ProjectMetrics", "gross_profit_usd", 959, 132, 269),
                chart(pid, "selected-project-values", "Budget, cost and completion estimate", "clusteredColumnChart",
                      ("ProjectMetrics", "project_name", "Project"),
                      [("ProjectMetrics", "approved_budget_usd", "Approved budget"),
                       ("ProjectMetrics", "actual_cost_usd", "Actual cost"),
                       ("ProjectMetrics", "estimate_at_completion_usd", "EAC")], 52, 277, 465, 392),
                table(pid, "project-record", "Project record",
                      [("ProjectMetrics", "project_name", "Project", False),
                       ("ProjectMetrics", "status", "Status", False),
                       ("ProjectMetrics", "financial_health", "Health", False),
                       ("ProjectMetrics", "approved_budget_usd", "Budget", True),
                       ("ProjectMetrics", "actual_cost_usd", "Cost", True),
                       ("ProjectMetrics", "recognized_revenue_usd", "Revenue", True),
                       ("ProjectMetrics", "gross_profit_usd", "Profit", True),
                       ("ProjectMetrics", "estimate_to_complete_usd", "ETC", True),
                       ("ProjectMetrics", "estimate_at_completion_usd", "EAC", True)],
                      535, 277, 693, 392),
            ]
        else:
            cards([("Rejected rows", "AuditSummary", "rejected_rows"),
                   ("Source rows", "AuditSummary", "source_rows"),
                   ("Reconciliation delta", "AuditSummary", "reconciliation_delta_usd"),
                   ("Holdout MAE", "AuditSummary", "holdout_mae_usd")])
            visuals += [
                chart(pid, "rejections", "Rejected rows by reason", "clusteredBarChart",
                      ("AuditIssues", "reason", "Reason"),
                      [("AuditIssues", "rejected_rows", "Rejected rows")], 52, 277, 560, 392),
                table(pid, "source-inventory", "Source inventory",
                      [("AuditSources", "source", "Source", False),
                       ("AuditSources", "rows", "Rows", True),
                       ("AuditSources", "modified_utc", "Modified UTC", False)],
                      630, 277, 598, 392),
            ]

        for visual in visuals:
            write_json(visual_dir / visual["name"] / "visual.json", visual)

    write_json(PAGES / "pages.json", {"$schema": SCHEMA_PAGES, "pageOrder": order,
                                       "activePageName": order[0]})


def register_theme() -> None:
    source = PBI / "theme" / "finance_theme.json"
    target = REPORT / "StaticResources" / "RegisteredResources" / "FinanceTheme.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    report_path = DEFINITION / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["themeCollection"]["customTheme"] = {
        "name": "FinanceTheme",
        "reportVersionAtImport": report["themeCollection"]["baseTheme"]["reportVersionAtImport"],
        "type": "RegisteredResources"}
    report["resourcePackages"] = [p for p in report["resourcePackages"] if p["name"] != "RegisteredResources"]
    report["resourcePackages"].append({"name": "RegisteredResources", "type": "RegisteredResources",
                                       "items": [{"name": "FinanceTheme", "path": "FinanceTheme.json", "type": "CustomTheme"}]})
    write_json(report_path, report)


def main() -> None:
    if not (PBI / "Financial Project Performance.pbip").exists():
        raise SystemExit("Open and save the PBIP shell in Power BI Desktop first")
    marts = make_marts()
    embed_project_metrics()
    for name, columns in marts.items():
        (TABLES / f"{name}.tmdl").write_text(tmdl_for_csv(name, columns), encoding="utf-8")
    build_pages()
    register_theme()
    print(f"Built 7 PBIR pages and {len(marts)} reporting marts in {PBI}")


if __name__ == "__main__":
    main()

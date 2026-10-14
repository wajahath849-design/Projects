"""Check the editable Power BI project against the curated extracts."""

from __future__ import annotations

import base64
import csv
import io
import json
import re
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data" / "curated"
PAGES = ROOT / "powerbi" / "Financial Project Performance.Report" / "definition" / "pages"
TABLES = ROOT / "powerbi" / "Financial Project Performance.SemanticModel" / "definition" / "tables"
REPORT_TABLES = ("ProjectMetrics", "MonthlyFinance", "ExpenseDrivers", "ForecastMonthly",
                 "AuditIssues", "AuditSources", "AuditSummary")


def snapshot_bytes(name: str) -> bytes:
    model = (TABLES / f"{name}.tmdl").read_text(encoding="utf-8")
    matches = re.findall(r'Binary\.FromText\("([A-Za-z0-9+/=]+)", BinaryEncoding\.Base64\)', model)
    assert len(matches) == 1, f"Missing portable snapshot for {name}"
    assert "File.Contents(" not in model, name
    data = base64.b64decode(matches[0], validate=True)
    generated = CURATED / f"{name}.csv"
    if generated.exists():
        assert data == generated.read_bytes(), f"Embedded data differs from {generated}"
    return data


def rows(name: str) -> list[dict[str, str]]:
    with io.StringIO(snapshot_bytes(name).decode("utf-8-sig"), newline="") as handle:
        return list(csv.DictReader(handle))


def total(data: list[dict[str, str]], column: str) -> Decimal:
    return sum((Decimal(row[column]) for row in data), Decimal(0))


def close_amount(left: Decimal, right: Decimal, label: str) -> None:
    assert abs(left - right) <= Decimal("0.05"), f"{label}: {left} != {right}"


def main() -> None:
    project = rows("ProjectMetrics")
    monthly = rows("MonthlyFinance")
    drivers = rows("ExpenseDrivers")
    forecast = rows("ForecastMonthly")
    issues = rows("AuditIssues")
    audit = rows("AuditSummary")
    assert len(project) == 40
    assert len(audit) == 1
    close_amount(total(project, "actual_cost_usd"), total(monthly, "actual_cost_usd"), "Monthly cost")
    close_amount(total(project, "actual_cost_usd"), total(drivers, "actual_cost_usd"), "Expense cost")
    close_amount(total(project, "recognized_revenue_usd"),
                 total(monthly, "recognized_revenue_usd"), "Monthly revenue")
    close_amount(total(project, "gross_profit_usd"),
                 total(project, "recognized_revenue_usd") - total(project, "actual_cost_usd"),
                 "Gross profit")
    close_amount(total(project, "estimate_to_complete_usd"),
                 total(forecast, "base_cost_usd"), "Base forecast")
    assert total(issues, "rejected_rows") == Decimal(audit[0]["rejected_rows"]) == 4
    assert Decimal(audit[0]["reconciliation_delta_usd"]) == 0

    pages_metadata = json.loads((PAGES / "pages.json").read_text(encoding="utf-8"))
    page_ids = pages_metadata["pageOrder"]
    assert len(page_ids) == len(set(page_ids)) == 7
    headers = {name: set(rows(name)[0]) for name in REPORT_TABLES}
    visual_count = 0
    for page_id in page_ids:
        page_dir = PAGES / page_id
        assert (page_dir / "page.json").exists(), page_id
        visuals = list((page_dir / "visuals").glob("*/visual.json"))
        assert len(visuals) >= 7, page_id
        visual_count += len(visuals)
        has_footer = False
        for path in visuals:
            visual = json.loads(path.read_text(encoding="utf-8"))["visual"]
            if "Synthetic demonstration data" in json.dumps(visual):
                has_footer = True
            query = visual.get("query", {}).get("queryState", {})
            for role in query.values():
                for field in role.get("projections", []):
                    expr = field["field"]
                    col = expr.get("Column") or expr.get("Aggregation", {}).get("Expression", {}).get("Column")
                    assert col, path
                    table = col["Expression"]["SourceRef"]["Entity"]
                    column = col["Property"]
                    assert column in headers[table], f"{path}: {table}.{column}"
                    if visual["visualType"] == "tableEx":
                        assert "active" not in field, f"Table projection marked active: {path}"
        assert has_footer, page_id

    print(f"Validated {len(page_ids)} pages, {visual_count} visuals, 40 projects, "
          f"and reconciled cost, revenue, profit, forecast, and audit marts.")


if __name__ == "__main__":
    main()

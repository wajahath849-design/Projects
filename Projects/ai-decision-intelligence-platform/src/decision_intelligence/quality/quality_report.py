"""Write portable JSON, CSV, and HTML data-quality reports."""

from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict
from pathlib import Path

from decision_intelligence.quality.data_quality import DataQualityReport


def write_quality_reports(report: DataQualityReport, output_directory: Path) -> dict[str, Path]:
    """Write all report formats atomically enough for local pipeline handoff."""
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = f"quality_{report.pipeline_run_id}"
    json_path = output_directory / f"{stem}.json"
    csv_path = output_directory / f"{stem}.csv"
    html_path = output_directory / f"{stem}.html"
    payload = {
        "pipeline_run_id": str(report.pipeline_run_id),
        "created_at": report.created_at.isoformat(),
        "passed": report.passed,
        "critical_failure_count": len(report.critical_failures),
        "results": [
            {**asdict(result), "check_id": str(result.check_id)} for result in report.results
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    fieldnames = [
        "check_id",
        "check_name",
        "table_name",
        "category",
        "severity",
        "status",
        "records_checked",
        "failed_records",
        "failure_percentage",
        "description",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in report.results:
            row = asdict(result)
            row["check_id"] = str(result.check_id)
            writer.writerow(row)
    table_rows = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(value))}</td>"
            for value in (
                result.check_name,
                result.table_name,
                result.category,
                result.severity,
                result.status,
                result.records_checked,
                result.failed_records,
                f"{result.failure_percentage:.4f}%",
                result.description,
            )
        )
        + "</tr>"
        for result in report.results
    )
    html_document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Data Quality Report</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;color:#172033}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccd3df;padding:.5rem;text-align:left}}
th{{background:#e9eef7}}.pass{{color:#176b3a}}</style></head><body>
<h1>AI Decision Intelligence Platform — Data Quality</h1>
<p>Run: {html.escape(str(report.pipeline_run_id))}</p>
<p class="pass">Critical gate: {"PASSED" if report.passed else "FAILED"}</p>
<table><thead><tr><th>Check</th><th>Table</th><th>Category</th><th>Severity</th>
<th>Status</th><th>Checked</th><th>Failed</th><th>Failure %</th><th>Description</th>
</tr></thead><tbody>{table_rows}</tbody></table></body></html>"""
    html_path.write_text(html_document, encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "html": html_path}

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from .config import get_settings
from .database import create_database_engine, initialize_database, query_to_csv
from .logging_config import configure_logging
from .pipeline import run_pipeline
from .transformer import transform_company_facts
from .validation import quality_summary, validate_financial_facts

app = typer.Typer(help="Apple SEC financial ETL and SQL reporting platform.")
console = Console()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@app.command("init-db")
def init_db() -> None:
    """Create the SQL Server database, schemas, tables, indexes and reporting views."""
    settings = get_settings()
    configure_logging(settings.log_level)
    initialize_database(settings, _project_root() / "sql")
    console.print(f"[green]Database initialized:[/green] {settings.mssql_database}")


@app.command()
def run(
    years: int | None = typer.Option(None, min=1, max=30, help="Years of history to retain."),
    force_refresh: bool = typer.Option(False, help="Ignore the local SEC response cache."),
    csv_only: bool = typer.Option(
        False, help="Write curated CSV files without loading SQL Server."
    ),
) -> None:
    """Download, transform, validate and load Apple financial facts."""
    settings = get_settings()
    configure_logging(settings.log_level)
    result = run_pipeline(settings, years, force_refresh, csv_only)

    table = Table(title="ETL Result")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Run ID", result.run_id)
    table.add_row("Financial facts", str(result.fact_count))
    table.add_row("Quality errors", str(result.error_count))
    table.add_row("Quality warnings", str(result.warning_count))
    table.add_row("SQL Server loaded", str(result.database_loaded))
    table.add_row("Facts CSV", str(result.facts_csv))
    table.add_row("Issues CSV", str(result.issues_csv))
    console.print(table)


@app.command()
def validate(
    csv_path: Path = typer.Argument(..., exists=True, readable=True, help="Curated facts CSV."),
) -> None:
    """Run data-quality checks against an existing curated facts CSV."""
    df = pd.read_csv(csv_path)
    issues = validate_financial_facts(df)
    summary = quality_summary(issues)
    console.print(
        f"Errors: [red]{summary['errors']}[/red] | "
        f"Warnings: [yellow]{summary['warnings']}[/yellow] | Total: {summary['total']}"
    )
    if not issues.empty:
        console.print(issues.to_string(index=False))


@app.command()
def export(
    output_dir: Path = typer.Option(Path("data/exports"), help="Destination directory."),
) -> None:
    """Export curated SQL views to CSV for sharing or offline Power BI development."""
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_database_engine(settings)
    exports = {
        "financial_facts.csv": "SELECT * FROM reporting.vw_FinancialFacts",
        "financial_summary.csv": "SELECT * FROM reporting.vw_FinancialSummary",
        "etl_run_history.csv": "SELECT * FROM reporting.vw_ETLRunHistory",
        "data_quality_issues.csv": "SELECT * FROM reporting.vw_DataQualityIssues",
    }
    for filename, query in exports.items():
        row_count = query_to_csv(engine, query, output_dir / filename)
        console.print(f"[green]Exported[/green] {row_count} rows -> {output_dir / filename}")


@app.command()
def sample(
    output_dir: Path = typer.Option(Path("data/sample"), help="Destination directory."),
) -> None:
    """Generate an offline demonstration dataset from the included SEC-shaped fixture."""
    fixture = _project_root() / "tests" / "fixtures" / "companyfacts_minimal.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    facts = transform_company_facts(payload, history_years=10, as_of_year=2025)
    issues = validate_financial_facts(facts)
    output_dir.mkdir(parents=True, exist_ok=True)
    facts_path = output_dir / "offline_sample_financial_facts.csv"
    issues_path = output_dir / "offline_sample_quality_issues.csv"
    facts.to_csv(facts_path, index=False)
    issues.to_csv(issues_path, index=False)
    console.print(f"[green]Created[/green] {len(facts)} sample facts -> {facts_path}")
    console.print(f"[green]Created[/green] {len(issues)} quality issues -> {issues_path}")


if __name__ == "__main__":
    app()

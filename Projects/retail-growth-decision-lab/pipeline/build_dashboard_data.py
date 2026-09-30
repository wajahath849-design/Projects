"""Assemble bounded reviewed outputs and provenance for the dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL = ROOT / "models"
TARGET = ROOT / "dashboard" / "src" / "data.json"
SOURCE_URL = "https://archive.ics.uci.edu/dataset/352/online+retail"


def records(path: Path) -> list[dict]:
    frame = pd.read_csv(path, dtype={"customer_id": "string"})
    return json.loads(frame.to_json(orient="records"))


def source(label: str, files: list[str], description: str, definitions: list[dict], *, sql: str | None = None,
           methods: list[dict] | None = None) -> dict:
    value = {
        "label": label, "description": description, "url": SOURCE_URL,
        "license": "CC BY 4.0", "files": files,
        "coverage": {"startDate": "2010-12-01", "endDate": "2011-12-09"},
        "executedAt": datetime.now(timezone.utc).isoformat(),
        "metricDefinitions": definitions,
        "evidenceFlow": [
            {"title": "Official source", "detail": "UCI Online Retail, Chen (2015), DOI 10.24432/C5BW33."},
            {"title": "Audited extraction", "detail": "Exact duplicates removed; merchandise sales, returns and excluded non-merchandise lines classified with deterministic rules."},
            {"title": "Reviewed output", "detail": description},
        ],
    }
    if sql is not None:
        value["sql"] = sql
    if methods:
        value["methods"] = methods
    return value


def definition(label, definition, component_ids, formula=None):
    value = {"label": label, "definition": definition, "componentIds": component_ids}
    if formula:
        value["formula"] = formula
    return value


def main():
    summary = json.loads((DATA / "processed/eur/summary.json").read_text(encoding="utf-8"))
    currency_audit = json.loads((DATA / "processed/eur/currency_audit.json").read_text(encoding="utf-8"))
    quality = json.loads((DATA / "quality.json").read_text(encoding="utf-8"))
    model_card = json.loads((MODEL / "model_card.json").read_text(encoding="utf-8"))
    monthly = records(DATA / "processed/eur/monthly.csv")
    countries = records(DATA / "processed/eur/countries.csv")
    cohorts = records(DATA / "processed/cohorts.csv")
    metrics = records(MODEL / "metrics.csv")
    gains = records(MODEL / "gains.csv")
    calibration = records(MODEL / "calibration.csv")
    intervals = records(MODEL / "intervals.csv")
    segments = records(MODEL / "segments.csv")
    candidates = records(MODEL / "candidates_eur.csv")
    summary_rows = [{**summary, "anonymous_sales_share": 1-summary["identified_sales_share"]}]
    quality_rows = [
        {"check": "Source rows", "value": quality["raw_rows"], "detail": "Rows in the original workbook"},
        {"check": "Exact duplicate rows removed", "value": quality["exact_duplicate_rows_removed"], "detail": "Exact matches across all eight source columns; first row retained"},
        {"check": "Retained sale rows", "value": quality["sale_rows"], "detail": "Positive-price merchandise sales, including anonymous sales"},
        {"check": "Return rows", "value": quality["return_rows"], "detail": "Negative merchandise quantities valued on their recorded date"},
        {"check": "Excluded rows", "value": quality["excluded_rows"], "detail": "Invalid, non-merchandise or non-positive-price rows"},
        {"check": "Of retained sales: anonymous", "value": quality["anonymous_sale_rows"], "detail": "Subset of sales above; excluded from customer analysis"},
    ]
    shared_methods = [{"language":"Python/SQL", "code":"See pipeline/ingest.py, pipeline/analytics.py and the named SQL file. Source checksums are recorded in data/source_manifest.json."}]
    queries = {
        "summary": {"rows": summary_rows, "source": source("UCI Online Retail — complete-month commercial summary", ["data/summary.json"],
            "Observed merchandise transactions from 1 Dec 2010 through 30 Nov 2011. December 2011 is excluded because it ends on 9 Dec.", [
                definition("Gross merchandise sales", "Positive-quantity catalogue merchandise with a positive price; includes transactions without a customer ID.", ["gross-sales","monthly-sales","country-sales"]),
                definition("Returns value", "Absolute recorded value of negative-quantity catalogue merchandise on its return date; no inferred link to an original sale.", ["returns-value","monthly-sales"]),
                definition("Net merchandise revenue", "Gross merchandise sales minus recorded merchandise returns. This is not profit.", ["net-sales","monthly-sales"], "gross_sales - returns_value"),
                definition("Identified sales share", "Share of gross merchandise sales attached to a valid customer ID.", ["identified-share"]),
            ], methods=shared_methods)},
        "monthly": {"rows": monthly, "source": source("Monthly commercial performance", ["data/processed/monthly.csv","sql/monthly.sql","sql/monthly_growth.sql"],
            "Complete monthly merchandise sales, returns, orders and identified customers. December 2011 is intentionally excluded.", [
                definition("Month-over-month net sales growth", "Current complete-month net merchandise revenue divided by the previous complete month, minus one.", ["monthly-sales"], "net_sales / previous_month_net_sales - 1"),
                definition("Returning-customer revenue share", "Share of identified gross order revenue from customers after their first observed purchase month.", ["customer-mix"]),
            ], sql=(ROOT/"sql/monthly_growth.sql").read_text(encoding="utf-8"), methods=shared_methods)},
        "countries": {"rows": countries, "source": source("Country performance", ["data/processed/countries.csv","sql/countries.sql"],
            "Gross merchandise sales and orders by recorded country for complete months.", [definition("Country gross sales", "Positive catalogue merchandise sales grouped by recorded country.", ["country-sales"])],
            sql=(ROOT/"sql/countries.sql").read_text(encoding="utf-8"), methods=shared_methods)},
        "cohorts": {"rows": cohorts, "source": source("First-observed-purchase cohorts", ["data/processed/cohorts.csv","sql/cohorts.sql"],
            "Identified customers grouped by first observed purchase month. Only mature cohort ages are emitted; future cells remain absent.", [
                definition("Cohort retention", "Customers purchasing at a given age month divided by the original first-observed-purchase cohort size.", ["cohort-retention"], "customers / cohort_size")],
            sql=(ROOT/"sql/cohorts.sql").read_text(encoding="utf-8"), methods=shared_methods)},
        "quality": {"rows": quality_rows, "source": source("Data quality audit", ["data/quality.json","pipeline/ingest.py"],
            "Deterministic row classification and population reconciliation for the original workbook.", [], methods=shared_methods)},
        "model_metrics": {"rows": metrics, "source": source("Out-of-time model evaluation", ["models/metrics.csv","models/model_card.json","pipeline/model.py"],
            "Validation selected the model; October calibrated probabilities; November is the untouched 30-day test window.", [
                definition("Average precision", "Area under the precision-recall curve; prevalence is the no-skill reference.", ["model-scorecard"]),
                definition("Lift at top 20%", "Precision among the highest-ranked 20% divided by the test purchase rate.", ["model-scorecard","gains-chart"], "precision_at_20 / prevalence"),
                definition("Brier score", "Mean squared difference between predicted probability and observed outcome; lower is better.", ["model-scorecard","calibration-chart"]),
            ], methods=[{"language":"Python", "code":"Time-snapshot features; validation model selection; independent calibration month; untouched November test. Customer ID is excluded from predictors."}])},
        "model_gains": {"rows": gains, "source": source("Targeting gains", ["models/gains.csv"], "Captured future purchasers at increasing contact fractions on the November test population.", [], methods=shared_methods)},
        "calibration": {"rows": calibration, "source": source("Probability calibration", ["models/calibration.csv"], "Mean prediction versus observed 30-day purchase rate in populated probability bins.", [], methods=shared_methods)},
        "intervals": {"rows": intervals, "source": source("Bootstrap uncertainty", ["models/intervals.csv"], "Paired customer bootstrap intervals for November sampling variation; they do not cover seasonal or causal uncertainty.", [], methods=shared_methods)},
        "segments": {"rows": segments, "source": source("Behavioral-segment diagnostics", ["models/segments.csv"], "Model calibration diagnostics for recency-defined Active, Cooling and Dormant groups.", [], methods=shared_methods)},
        "candidates": {"rows": candidates, "source": source("November customer priorities", ["models/candidates.csv","models/model_card.json"],
            "Known customers scored at 1 Nov 2011. Purchase probability is not treatment uplift; ranking is a transparent scenario heuristic.", [
                definition("Purchase probability", "Calibrated probability of at least one valid positive purchase in the next 30 days.", ["priority-table","scenario-economics"]),
                definition("Priority score", "Capped historical order value multiplied by one minus purchase probability. This is not a causal uplift estimate or proven optimal policy.", ["priority-table"], "order_value * (1 - purchase_probability)"),
            ], methods=[{"language":"Python", "code":"Score known customers using pre-cutoff features; cap historical order value at the training-period 95th percentile; order by the documented priority heuristic."}])},
    }
    for query_id, query in queries.items():
        if query_id in {"model_gains", "calibration", "intervals", "segments"}:
            query["source"]["methods"] = [{"language": "Python", "code": "Generated by pipeline/model.py from the November holdout; see models/model_card.json for temporal boundaries and limitations."}]
        query["methods"] = query["source"].pop("methods", [])
        if query_id in {"summary", "monthly", "countries", "candidates"}:
            replacements = {"data/summary.json": "data/processed/eur/summary.json",
                "data/processed/monthly.csv": "data/processed/eur/monthly.csv",
                "data/processed/countries.csv": "data/processed/eur/countries.csv",
                "models/candidates.csv": "models/candidates_eur.csv"}
            query["source"]["files"] = [replacements.get(p, p) for p in query["source"]["files"]]
            query["source"]["files"] += ["data/fx/ecb_gbp_per_eur.csv", "data/fx/source.json", "pipeline/currency.py"]
            query["source"]["evidenceFlow"].append({"title": "Historical EUR translation", "detail":
                "Source: European Central Bank daily reference rates, " + currency_audit["source_url"] +
                ". EUR = GBP / GBP-per-EUR rate on transaction calendar date; latest prior published rate for weekends/holidays. Monetary rows are EUR. Models retain source-GBP features and unchanged predictions."})
            query["methods"].append({"language": "python", "code": "python -m pipeline.currency\n# Translate each sale and return before aggregation. Recompute capped historical customer value from translated orders; retain GBP-trained purchase probabilities."})
            query["source"]["description"] += " Monetary amounts are EUR translated using historical ECB reference rates."
            query["source"]["metricDefinitions"].append({"label": "Currency", "definition":
                "EUR reporting translation from source GBP using transaction-date ECB rates. Campaign budget/contact cost inputs are EUR. Model probabilities are unchanged."})
    snapshot = {
        "id": "dashboard:cbe0a25f-922d-40b3-b5fa-96a611365f26", "surface": "dashboard",
        "title": "Retail Growth Decision Lab", "status": "reviewed", "buildStatus": "complete",
        "generatedAt": datetime.now(timezone.utc).isoformat(), "filters": [], "queries": queries,
        "model": model_card, "currency": currency_audit,
    }
    TARGET.write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET} with {len(candidates):,} scored customers")


if __name__ == "__main__":
    main()

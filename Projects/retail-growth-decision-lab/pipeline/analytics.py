"""Build reviewed commercial and retention outputs from the audited SQLite ledger.

Run from the project root: python -m pipeline.analytics
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "processed"
PARAMS = {"period_start": "2010-12-01", "period_end": "2011-12-01"}


def read_sql(name: str, connection: sqlite3.Connection, params: dict | None = None) -> pd.DataFrame:
    sql = (ROOT / "sql" / name).read_text(encoding="utf-8")
    return pd.read_sql_query(sql, connection, params=params or {})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    database = DATA / "retail.sqlite"
    if not database.exists():
        raise FileNotFoundError("Run python -m pipeline.ingest first")
    with sqlite3.connect(database) as connection:
        orders = read_sql("orders.sql", connection)
        orders.to_sql("orders", connection, if_exists="replace", index=False)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON orders(customer_id, invoice_date)")
        monthly = read_sql("monthly.sql", connection, PARAMS)
        monthly.to_sql("monthly", connection, if_exists="replace", index=False)
        monthly_growth = read_sql("monthly_growth.sql", connection, PARAMS)
        cohorts = read_sql("cohorts.sql", connection, {"period_end": PARAMS["period_end"]})
        countries = read_sql("countries.sql", connection, PARAMS)
        summary = pd.read_sql_query("""
            SELECT
              ROUND(SUM(CASE WHEN kind='sale' THEN line_revenue ELSE 0 END),2) AS gross_sales,
              ROUND(-SUM(CASE WHEN kind='return' THEN line_revenue ELSE 0 END),2) AS returns_value,
              ROUND(SUM(CASE WHEN kind IN ('sale','return') THEN line_revenue ELSE 0 END),2) AS net_sales,
              COUNT(DISTINCT CASE WHEN kind='sale' THEN invoice_no END) AS orders,
              COUNT(DISTINCT CASE WHEN kind='sale' AND customer_id IS NOT NULL THEN customer_id END) AS customers,
              ROUND(SUM(CASE WHEN kind='sale' AND customer_id IS NOT NULL THEN line_revenue ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN kind='sale' THEN line_revenue ELSE 0 END),0),6) AS identified_sales_share
            FROM line_items WHERE invoice_date>=:period_start AND invoice_date<:period_end
        """, connection, params=PARAMS).iloc[0].to_dict()
    for frame, name in [(orders, "orders"), (monthly_growth, "monthly"), (cohorts, "cohorts"), (countries, "countries")]:
        frame.to_csv(OUT / f"{name}.csv", index=False)
    # Independent reconciliation: monthly outputs must equal the complete-period ledger total.
    if abs(float(monthly.net_sales.sum()) - float(summary["net_sales"])) > 0.01:
        raise AssertionError("Monthly net sales do not reconcile to the ledger")
    if abs(float(countries.gross_sales.sum()) - float(summary["gross_sales"])) > 0.01:
        raise AssertionError("Country gross sales do not reconcile to the ledger")
    summary.update({
        "period_start": PARAMS["period_start"], "period_end_exclusive": PARAMS["period_end"],
        "currency": "GBP", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "latest_complete_month": "2011-11", "partial_month_excluded": "2011-12",
        "return_rate_of_gross": round(float(summary["returns_value"] / summary["gross_sales"]), 6),
        "average_order_value": round(float(summary["gross_sales"] / summary["orders"]), 2),
        "cohort_definition": "Month of first observed valid positive purchase by an identified customer.",
    })
    (DATA / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

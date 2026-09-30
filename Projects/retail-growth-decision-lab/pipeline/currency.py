"""Translate the audited GBP ledger into EUR using historical ECB daily rates.

GBP per EUR is the ECB quote: EUR = GBP / rate. Non-publication dates use
the most recent prior reference date. Models remain fitted in source GBP.
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline.analytics import PARAMS, read_sql
from pipeline.model import TRAIN_DATES, TEST_DATE, build_features, scenario

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "data/fx"
OUT = ROOT / "data/processed/eur"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
ECB_PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_rates() -> pd.DataFrame:
    FX.mkdir(parents=True, exist_ok=True)
    target, manifest = FX / "ecb_gbp_per_eur.csv", FX / "source.json"
    if not target.exists():
        cached = ROOT / "data/raw/ecb-eurofxref-hist.zip"
        if cached.exists():
            archive = cached.read_bytes()
        else:
            with urllib.request.urlopen(ECB_URL, timeout=90) as response:
                archive = response.read()
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            frame = pd.read_csv(z.open("eurofxref-hist.csv"), skipinitialspace=True)
        frame.columns = frame.columns.str.strip()
        frame = frame.loc[frame.Date.between("2010-11-24", "2011-12-09"), ["Date", "GBP"]]
        frame = frame.rename(columns={"Date": "rate_date", "GBP": "gbp_per_eur"}).sort_values("rate_date")
        frame.to_csv(target, index=False)
        manifest.write_text(json.dumps({"provider": "European Central Bank", "source_url": ECB_PAGE,
            "download_url": ECB_URL, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "archive_sha256": digest(archive), "subset_sha256": digest(target.read_bytes()),
            "quote": "GBP per 1 EUR", "conversion": "EUR = GBP / gbp_per_eur",
            "non_publication_dates": "Use latest published reference date on or before transaction calendar date",
            "purpose": "Historical reporting translation; not a transaction execution rate",
            "first_rate_date": frame.rate_date.min(), "last_rate_date": frame.rate_date.max()}, indent=2)+"\n")
    metadata = json.loads(manifest.read_text())
    if digest(target.read_bytes()) != metadata["subset_sha256"]:
        raise ValueError("ECB rate snapshot checksum mismatch")
    frame = pd.read_csv(target, parse_dates=["rate_date"])
    if frame.rate_date.duplicated().any() or frame.gbp_per_eur.isna().any() or (frame.gbp_per_eur <= 0).any():
        raise ValueError("Invalid ECB rate snapshot")
    return frame


def translate(lines: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    frame = lines.copy()
    frame["transaction_date"] = pd.to_datetime(frame.invoice_date).dt.normalize()
    frame = pd.merge_asof(frame.sort_values("transaction_date"), rates.sort_values("rate_date"),
                          left_on="transaction_date", right_on="rate_date", direction="backward")
    age = (frame.transaction_date - frame.rate_date).dt.days
    if frame.gbp_per_eur.isna().any() or (age > 7).any() or (age < 0).any():
        raise ValueError("Missing or stale historical FX rate")
    frame["line_revenue_gbp"] = frame.line_revenue
    frame["line_revenue"] = frame.line_revenue / frame.gbp_per_eur
    if "unit_price" in frame:
        frame["unit_price"] = frame.unit_price / frame.gbp_per_eur
    return frame


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rates = load_rates()
    with sqlite3.connect(ROOT / "data/retail.sqlite") as con:
        lines = pd.read_sql_query("SELECT * FROM line_items WHERE kind IN ('sale','return')", con)
    eur = translate(lines, rates)
    with sqlite3.connect(":memory:") as con:
        eur.drop(columns=["transaction_date", "rate_date"]).to_sql("line_items", con, index=False)
        orders = read_sql("orders.sql", con)
        orders.to_sql("orders", con, index=False)
        monthly = read_sql("monthly.sql", con, PARAMS)
        monthly.to_sql("monthly", con, index=False)
        growth = read_sql("monthly_growth.sql", con, PARAMS)
        countries = read_sql("countries.sql", con, PARAMS)
    for name, frame in [("orders", orders), ("monthly", growth), ("countries", countries)]:
        frame.to_csv(OUT / f"{name}.csv", index=False)
    reporting = eur[eur.invoice_date.between(PARAMS["period_start"], PARAMS["period_end"], inclusive="left")]
    sales = reporting[reporting.kind == "sale"]
    gross = float(sales.line_revenue.sum())
    returns = -float(reporting.loc[reporting.kind == "return", "line_revenue"].sum())
    summary = json.loads((ROOT / "data/summary.json").read_text())
    summary.update(currency="EUR", gross_sales=round(gross, 2), returns_value=round(returns, 2),
                   net_sales=round(gross-returns, 2),
                   identified_sales_share=float(sales.loc[sales.customer_id.notna(), "line_revenue"].sum()/gross),
                   return_rate_of_gross=returns/gross, average_order_value=gross/summary["orders"])
    assert abs(monthly.net_sales.sum()-summary["net_sales"]) < .01
    assert abs(countries.gross_sales.sum()-summary["gross_sales"]) < .01
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")

    # Preserve trained-model probabilities, but recompute historical value in EUR.
    orders["invoice_date"] = pd.to_datetime(orders.invoice_date)
    train = pd.concat([build_features(orders, d, include_label=False) for d in TRAIN_DATES])
    features = build_features(orders, TEST_DATE, include_label=False)
    candidates = pd.read_csv(ROOT / "models/candidates.csv", dtype={"customer_id": str})
    cap = float(train.order_value.quantile(.95))
    values = features[["customer_id", "order_value", "spend_90d"]].copy()
    values["order_value"] = values.order_value.clip(upper=cap)
    candidates = candidates.drop(columns=["order_value", "spend_90d", "priority_score"]).merge(values, on="customer_id", validate="one_to_one")
    candidates["priority_score"] = candidates.order_value * (1-candidates.purchase_probability)
    candidates["currency"] = "EUR"
    candidates.sort_values(["priority_score", "customer_id"], ascending=[False, True], inplace=True)
    candidates.to_csv(ROOT / "models/candidates_eur.csv", index=False)
    mapping = eur[["transaction_date", "rate_date", "gbp_per_eur"]].drop_duplicates().sort_values("transaction_date")
    mapping.to_csv(FX / "transaction_date_mapping.csv", index=False)
    audit = {"source_currency": "GBP", "display_currency": "EUR", "source_url": ECB_PAGE,
             "translation": "Each sale/return translated at its recorded calendar date; prior available ECB rate on non-publication days",
             "rows_translated": len(eur), "rows_using_prior_rate": int((eur.rate_date < eur.transaction_date).sum()),
             "maximum_rate_age_days": int((eur.transaction_date-eur.rate_date).dt.days.max()),
             "eur_order_value_cap": cap, "model_feature_currency": "GBP", "model_refit": False,
             "default_eur_scenario": scenario(candidates), "summary": summary}
    (OUT / "currency_audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()

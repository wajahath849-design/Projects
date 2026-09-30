"""Download the original UCI workbook and build an audited SQLite line ledger.

Run from the project root: python -m pipeline.ingest
The workbook and archive are immutable inputs: cached files are checksum-verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/352/online+retail"
COLUMN_MAP = {
    "InvoiceNo": "invoice_no", "StockCode": "stock_code",
    "Description": "description", "Quantity": "quantity",
    "InvoiceDate": "invoice_date", "UnitPrice": "unit_price",
    "CustomerID": "customer_id", "Country": "country",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def acquire_source(data_dir: Path = DATA) -> Path:
    """Fetch only the named member, avoiding arbitrary archive path extraction."""
    raw = data_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / "online-retail.zip"
    workbook = raw / "Online Retail.xlsx"
    manifest_path = data_dir / "source_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for path, key in [(archive, "archive_sha256"), (workbook, "workbook_sha256")]:
            if path.exists() and sha256(path) != manifest[key]:
                raise ValueError(f"Source checksum changed: {path}. Restore the original input before rebuilding.")
    if not archive.exists():
        partial = archive.with_suffix(".zip.part")
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "RetailGrowthLab/1.0 (educational portfolio)"})
        try:
            with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as target:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 100_000_000:
                        raise ValueError("Unexpected source archive size (over 100 MB).")
                    target.write(chunk)
            partial.replace(archive)
        finally:
            if partial.exists():
                partial.unlink()
    if not workbook.exists():
        with zipfile.ZipFile(archive) as source:
            member = source.getinfo("Online Retail.xlsx")
            if member.file_size > 100_000_000:
                raise ValueError("Unexpected workbook size (over 100 MB).")
            # Do not use extractall: only a verified fixed filename is written.
            with source.open(member) as content, workbook.open("wb") as target:
                shutil.copyfileobj(content, target)
    if not manifest_path.exists():
        write_json(manifest_path, {
            "dataset": "Online Retail", "creator": "Daqing Chen", "year": 2015,
            "citation": "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33",
            "doi": "https://doi.org/10.24432/C5BW33", "source_page": SOURCE_PAGE,
            "download_url": SOURCE_URL, "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "archive_sha256": sha256(archive), "workbook_sha256": sha256(workbook),
            "archive_bytes": archive.stat().st_size, "workbook_bytes": workbook.stat().st_size,
            "expected_source_rows": 541909,
        })
    # Recheck newly reconstructed files against the recorded fingerprints as well.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256(archive) != manifest["archive_sha256"] or sha256(workbook) != manifest["workbook_sha256"]:
        raise ValueError("Downloaded/extracted source does not match the recorded checksum.")
    return workbook


def clean_lines(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Classify every unique source line, keeping excluded lines for audit.

    Catalogue merchandise is explicitly scoped to a five-digit stock code with
    an optional alphabetic suffix. This excludes postage, fees, adjustments,
    manual codes and gift-voucher codes from merchandise revenue. Cancellation
    values are booked on their recorded date; no sale/refund linkage is inferred.
    """
    missing = sorted(set(COLUMN_MAP) - set(raw.columns))
    if missing:
        raise ValueError(f"Source is missing required columns: {missing}")
    raw = raw[list(COLUMN_MAP)].copy()
    duplicate = raw.duplicated(keep="first")
    frame = raw.loc[~duplicate].rename(columns=COLUMN_MAP).copy()
    frame.insert(0, "source_row", frame.index.to_numpy() + 2)
    for col in ["invoice_no", "stock_code", "country"]:
        frame[col] = frame[col].astype("string").str.strip()
    frame["stock_code"] = frame["stock_code"].str.upper()
    frame["invoice_no"] = frame["invoice_no"].str.upper()
    customer = pd.to_numeric(frame["customer_id"], errors="coerce")
    invalid_customer = customer.notna() & ((customer <= 0) | (customer % 1 != 0))
    frame["customer_id"] = customer.mask(invalid_customer).astype("Int64").astype("string")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce")
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="coerce")
    frame["line_revenue"] = frame["quantity"] * frame["unit_price"]
    cancel = frame["invoice_no"].str.startswith("C", na=False)
    catalogue = frame["stock_code"].str.fullmatch(r"\d{5}[A-Z]*", na=False)
    valid_invoice = frame["invoice_no"].str.fullmatch(r"C?\d+", na=False)
    invalid_fields = (
        frame["invoice_date"].isna() | ~valid_invoice |
        frame["country"].isna() | frame["country"].eq("") |
        ~np.isfinite(frame["quantity"]) | ~np.isfinite(frame["unit_price"])
    )
    reason = pd.Series("", index=frame.index, dtype="string")
    # Mutually exclusive reasons with an explicit precedence, so counts reconcile.
    for mask, label in [
        (invalid_fields, "invalid_required_field"),
        (~catalogue, "non_merchandise_code"),
        (frame["unit_price"] <= 0, "non_positive_price"),
        (frame["quantity"] == 0, "zero_quantity"),
        (cancel & (frame["quantity"] > 0), "cancellation_with_positive_quantity"),
    ]:
        reason.loc[reason.eq("") & mask] = label
    frame["exclusion_reason"] = reason
    frame["kind"] = "excluded"
    frame.loc[reason.eq("") & (frame["quantity"] > 0), "kind"] = "sale"
    frame.loc[reason.eq("") & (frame["quantity"] < 0), "kind"] = "return"
    sales = frame[frame["kind"].eq("sale")]
    returns = frame[frame["kind"].eq("return")]
    identified = sales[sales["customer_id"].notna()]
    anonymous = sales[sales["customer_id"].isna()]
    audit = {
        "raw_rows": int(len(raw)), "exact_duplicate_rows_removed": int(duplicate.sum()),
        "unique_rows": int(len(frame)), "sale_rows": int(len(sales)),
        "return_rows": int(len(returns)), "excluded_rows": int(frame["kind"].eq("excluded").sum()),
        "excluded_by_reason": {str(k): int(v) for k, v in reason[reason.ne("")].value_counts().items()},
        "non_merchandise_stock_codes": sorted(frame.loc[~catalogue, "stock_code"].dropna().unique().tolist()),
        "missing_customer_id_raw_rows": int(raw["CustomerID"].isna().sum()),
        "invalid_customer_id_unique_rows": int(invalid_customer.sum()),
        "missing_customer_id_unique_rows": int(frame["customer_id"].isna().sum()),
        "anonymous_sale_rows": int(len(anonymous)), "identified_sale_rows": int(len(identified)),
        "all_history_gross_sales": round(float(sales["line_revenue"].sum()), 2),
        "all_history_identified_gross_sales": round(float(identified["line_revenue"].sum()), 2),
        "all_history_anonymous_gross_sales": round(float(anonymous["line_revenue"].sum()), 2),
        "all_history_returns_value": round(float(-returns["line_revenue"].sum()), 2),
        "negative_quantity_without_c_prefix_rows": int(((frame["quantity"] < 0) & ~cancel & frame["kind"].eq("return")).sum()),
        "source_start": frame["invoice_date"].min().isoformat(),
        "source_end": frame["invoice_date"].max().isoformat(),
        "currency": "GBP",
        "rules": {
            "duplicates": "Remove exact duplicates across the eight original columns; retain the first source row. This is an explicit assumption: repeated identical lines cannot be verified as accidental from this source.",
            "merchandise": "StockCode must be five digits followed by zero or more letters. Non-catalogue charges, manual codes and gift vouchers are excluded from merchandise sales and returns.",
            "sales": "Positive quantity and positive unit price; valid invoice/date/country; invoice must not start with C.",
            "returns": "Negative quantity and positive unit price for the same merchandise scope. Record absolute value on the return invoice date; never match to an assumed original order.",
            "identity": "Anonymous sales remain in commercial totals, but cannot enter customer models or retention cohorts.",
            "revenue": "Gross merchandise sales less recorded merchandise returns is net merchandise revenue, not accounting revenue or profit. No costs or marketing spend are provided.",
            "period": "The final observed month (December 2011) is incomplete. Main commercial metrics and cohort maturity stop before 2011-12-01.",
        },
    }
    frame["invoice_date"] = frame["invoice_date"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return frame.reset_index(drop=True), audit


def ingest(source: Path, data_dir: Path = DATA) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"Reading original workbook: {source.name}", flush=True)
    raw = pd.read_excel(source, engine="openpyxl")
    lines, audit = clean_lines(raw)
    audit["source_workbook_sha256"] = sha256(source)
    database = data_dir / "retail.sqlite"
    with sqlite3.connect(database) as connection:
        lines.to_sql("line_items", connection, if_exists="replace", index=False, chunksize=20000)
        connection.executescript("""
            CREATE INDEX idx_lines_invoice ON line_items(invoice_no);
            CREATE INDEX idx_lines_date_kind ON line_items(invoice_date, kind);
            CREATE INDEX idx_lines_customer ON line_items(customer_id);
        """)
    write_json(data_dir / "quality.json", audit)
    print(f"Audited {audit['raw_rows']:,} rows -> {audit['unique_rows']:,} unique lines; wrote {database.name}", flush=True)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Use a local original workbook instead of downloading.")
    args = parser.parse_args()
    source = args.source or acquire_source()
    audit = ingest(source)
    if args.source is None and audit["raw_rows"] != 541909:
        raise ValueError("Unexpected row count for the pinned UCI dataset; investigate source drift.")


if __name__ == "__main__":
    main()

"""Prepare the local data and database after cloning the GitHub repository."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "release" / "processed_dataset.zip"
PROCESSED = ROOT / "data" / "processed"
REQUIRED = {
    "alerts.csv",
    "detected_anomalies.csv",
    "facilities.csv",
    "facility_health_scores.csv",
    "incident_reviews.csv",
    "maintenance_actions.csv",
    "network_metrics.csv",
    "power_metrics.csv",
    "powerbi_cost_carbon_snapshot.csv",
    "powerbi_incident_impact_snapshot.csv",
    "powerbi_live_operations_snapshot.csv",
    "server_failure_risk.csv",
    "server_metrics.csv",
    "servers.csv",
    "system_logs.csv",
    "uptime_incidents.csv",
}


def extract_dataset() -> str:
    existing = {path.name for path in PROCESSED.glob("*.csv")}
    if REQUIRED <= existing:
        return "Existing processed dataset retained."
    if not ARCHIVE.exists():
        raise FileNotFoundError(
            "Missing data/release/processed_dataset.zip. Download the repository "
            "release asset or place the processed CSV files in data/processed."
        )
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as bundle:
        members = [item for item in bundle.infolist() if not item.is_dir()]
        unsafe = [
            item.filename
            for item in members
            if Path(item.filename).name != item.filename
            or Path(item.filename).suffix.lower() != ".csv"
        ]
        if unsafe:
            raise ValueError(f"Unsafe dataset archive entries: {unsafe}")
        bundle.extractall(PROCESSED, members=members)
    missing = REQUIRED - {path.name for path in PROCESSED.glob("*.csv")}
    if missing:
        raise RuntimeError(f"Dataset archive is incomplete: {sorted(missing)}")
    return f"Extracted {len(members)} governed CSV files."


def main() -> None:
    print(extract_dataset())
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "load_database.py")],
        cwd=ROOT,
        check=True,
    )
    print("Local SQLite database is ready.")


if __name__ == "__main__":
    main()

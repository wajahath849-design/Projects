"""Apply Power BI views, export sample CSVs, and validate the construction package."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.database.connection import connect  # noqa: E402
from decision_intelligence.database.initializer import execute_script  # noqa: E402
from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

LOGGER = logging.getLogger(__name__)
VIEWS = (
    "vw_PBI_ExecutiveOverview", "vw_PBI_DemandForecast",
    "vw_PBI_InventoryIntelligence", "vw_PBI_OptimizationRecommendations",
    "vw_PBI_ScenarioComparison", "vw_PBI_ModelPerformance", "vw_PBI_DataQuality",
    "vw_PBI_ForecastExplanations",
)


def _validate_package() -> int:
    theme_path = PROJECT_ROOT / "powerbi" / "theme" / "decision_intelligence_theme.json"
    json.loads(theme_path.read_text(encoding="utf-8"))
    dax = (PROJECT_ROOT / "powerbi" / "dax" / "measures.dax").read_text(encoding="utf-8")
    measure_count = len(re.findall(r"(?m)^[A-Za-z][A-Za-z ]+\s*=\s*$", dax))
    if measure_count < 31:
        raise RuntimeError(f"Expected at least 31 DAX measures, found {measure_count}")
    required_docs = (
        "data_model.md", "page_layouts.md", "formatting_and_interactions.md",
    )
    for name in required_docs:
        if not (PROJECT_ROOT / "powerbi" / "docs" / name).is_file():
            raise RuntimeError(f"Missing Power BI document: {name}")
    return measure_count


def main() -> int:
    try:
        app, database = load_settings(PROJECT_ROOT)
        configure_logging(app.config_dir / "logging.yaml", app.log_level)
        output = PROJECT_ROOT / "powerbi" / "exports"
        output.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        with connect(database) as connection:
            execute_script(
                connection, PROJECT_ROOT / "powerbi" / "sql" / "power_bi_views.sql"
            )
            connection.commit()
            for view in VIEWS:
                cursor = connection.execute(f"SELECT * FROM dbo.{view}")
                columns = [column[0] for column in cursor.description]
                frame = pd.DataFrame.from_records(cursor.fetchall(), columns=columns)
                frame.to_csv(output / f"{view}.csv", index=False)
                counts[view] = len(frame)
        measure_count = _validate_package()
        (output / "manifest.json").write_text(json.dumps({
            "views": counts, "dax_measure_count": measure_count,
            "pbix_generated": False,
            "note": "Construction package and sample exports only; no PBIX is claimed.",
        }, indent=2), encoding="utf-8")
        print(f"power_bi_views={len(counts)}")
        print(f"dax_measures={measure_count}")
        print("POWER BI PACKAGE PASSED")
        return 0
    except Exception as exc:
        LOGGER.exception("Power BI export failed: %s", exc)
        print("POWER BI PACKAGE FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

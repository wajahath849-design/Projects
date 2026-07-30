from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from app import config
from app.db import connect
from app.model_registry import load_models, read_model_configs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing-models", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    configs = read_model_configs()

    for item in configs:
        class_map = config.BASE / item["class_map"]
        try:
            if len(json.loads(class_map.read_text(encoding="utf-8"))) != 10:
                errors.append(f"Class map does not contain 10 classes: {class_map}")
        except Exception as exc:
            errors.append(f"Invalid class map {class_map}: {exc}")

        if (
            item.get("enabled")
            and not (config.BASE / item["model_path"]).is_file()
            and not args.allow_missing_models
        ):
            errors.append(f"Enabled model file is missing: {item['model_path']}")

    try:
        with connect(retries=2) as conn:
            tables = {
                row[0]
                for row in conn.cursor().execute(
                    "SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo')"
                )
            }
        required = {
            "ModelRegistry",
            "ImageBatch",
            "ModelPrediction",
            "ClassProbability",
            "HumanReview",
            "SystemEvent",
        }
        if required - tables:
            errors.append("Missing database tables: " + ", ".join(sorted(required - tables)))
    except Exception as exc:
        errors.append(f"Database connection failed: {exc}")

    enabled = [item for item in configs if item.get("enabled")]
    if enabled and not errors and not args.allow_missing_models:
        result = load_models()
        for item, reason in result.unavailable:
            errors.append(f"{item['display_name']} could not load: {reason}")
    elif not enabled and not args.allow_missing_models:
        errors.append(
            "No model is enabled. Add trained models and run scripts/install_trained_models.py"
        )

    if errors:
        raise SystemExit("PROJECT VERIFICATION FAILED\n- " + "\n- ".join(errors))

    print(f"PROJECT VERIFICATION PASSED: {len(enabled)} enabled model(s).")


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
from datetime import datetime

import yaml

from app import config

MIN_ACCURACY = 0.90


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate metadata and enable trained model files.")
    parser.add_argument("--minimum-accuracy", type=float, default=MIN_ACCURACY)
    args = parser.parse_args()

    document = yaml.safe_load(config.MODEL_CONFIG.read_text(encoding="utf-8"))
    errors: list[str] = []
    enabled = 0
    for model in document["models"]:
        model_file = config.BASE / model["model_path"]
        metadata_file = config.BASE / model["metadata_path"]
        if not model_file.is_file() or not metadata_file.is_file():
            model.update(enabled=False, trained=False, verified=False, deployment_stage="AwaitingTraining")
            continue
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            validation = float(metadata["validation_accuracy"])
            test_accuracy = float(metadata["test_accuracy"])
            trained = bool(metadata.get("trained", True))
            verified = bool(metadata.get("verified", False)) and validation >= args.minimum_accuracy and test_accuracy >= args.minimum_accuracy
            if not trained or not verified:
                raise ValueError(f"accuracy/verification failed: validation={validation:.4f}, test={test_accuracy:.4f}")
            model.update(
                enabled=True, trained=True, verified=True, deployment_stage="Verified",
                validation_accuracy=round(validation, 6), test_accuracy=round(test_accuracy, 6),
                training_date=metadata.get("training_date") or metadata.get("created_at") or datetime.utcnow().isoformat(timespec="seconds"),
                version=str(metadata.get("model_version", "1.0.0")),
            )
            enabled += 1
        except Exception as exc:
            model.update(enabled=False, trained=False, verified=False, deployment_stage="Rejected")
            errors.append(f"{model['display_name']}: {exc}")
    config.MODEL_CONFIG.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    print(f"Enabled {enabled} verified model(s).")
    if errors:
        print("Rejected models:")
        for error in errors:
            print(" -", error)
    if enabled == 0:
        raise SystemExit("No trained model passed validation. Copy model and metadata files into models/ and rerun.")


if __name__ == "__main__":
    main()

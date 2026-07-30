from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from . import config
from .adapters import build_adapter
from .db import connect, write_event


@dataclass
class ModelLoadResult:
    loaded: dict[str, tuple[object, dict[str, Any]]]
    unavailable: list[tuple[dict[str, Any], str]]


def read_model_configs() -> list[dict[str, Any]]:
    data = yaml.safe_load(config.MODEL_CONFIG.read_text(encoding="utf-8")) or {}
    models = data.get("models")
    if not isinstance(models, list):
        raise ValueError("config/models.yml must contain a models list")
    keys: set[str] = set()
    for item in models:
        key = str(item.get("key", "")).strip()
        if not key or key in keys:
            raise ValueError(f"Missing or duplicate model key: {key!r}")
        keys.add(key)
    return models


def sync_registry(configs: list[dict[str, Any]]) -> dict[str, int]:
    model_ids: dict[str, int] = {}
    with connect() as conn:
        cursor = conn.cursor()
        for item in configs:
            width, height = (int(v) for v in item.get("input_size", [28, 28]))
            values = (
                item["display_name"], item["framework"], item.get("architecture", "unknown"),
                str(item.get("version", "1.0.0")), item["model_path"], item.get("dataset_key", "mnist"),
                width, height, int(item.get("channels", 1)), item.get("deployment_stage", "Development"),
                int(bool(item.get("enabled"))), int(bool(item.get("trained"))), int(bool(item.get("verified"))),
                item.get("validation_accuracy"), item.get("test_accuracy"), item.get("training_date"), item["key"],
            )
            existing = cursor.execute("SELECT ModelID FROM dbo.ModelRegistry WHERE ModelKey=?", item["key"]).fetchone()
            if existing:
                cursor.execute(
                    """UPDATE dbo.ModelRegistry SET ModelName=?,Framework=?,Architecture=?,ModelVersion=?,ModelPath=?,
                       DatasetName=?,InputWidth=?,InputHeight=?,InputChannels=?,DeploymentStage=?,IsEnabled=?,IsTrained=?,
                       IsVerified=?,ValidationAccuracy=?,TestAccuracy=?,TrainingDate=?,UpdatedAt=SYSUTCDATETIME()
                       WHERE ModelKey=?""", *values,
                )
                model_ids[item["key"]] = int(existing[0])
            else:
                inserted = cursor.execute(
                    """INSERT dbo.ModelRegistry(ModelName,Framework,Architecture,ModelVersion,ModelPath,DatasetName,
                       InputWidth,InputHeight,InputChannels,DeploymentStage,IsEnabled,IsTrained,IsVerified,
                       ValidationAccuracy,TestAccuracy,TrainingDate,ModelKey)
                       OUTPUT INSERTED.ModelID VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", *values,
                ).fetchone()
                model_ids[item["key"]] = int(inserted[0])
        conn.commit()
    return model_ids


def load_models() -> ModelLoadResult:
    configs = read_model_configs()
    model_ids = sync_registry(configs)
    loaded: dict[str, tuple[object, dict[str, Any]]] = {}
    unavailable: list[tuple[dict[str, Any], str]] = []
    for original in configs:
        if not original.get("enabled", False):
            continue
        item = dict(original)
        item["model_id"] = model_ids[item["key"]]
        path = config.BASE / str(item["model_path"])
        reason = None
        if not item.get("trained") or not item.get("verified"):
            reason = "model is not marked trained and verified"
        elif not path.is_file():
            reason = f"model file not found: {path}"
        if reason:
            unavailable.append((item, reason))
            continue
        try:
            loaded[item["key"]] = (build_adapter(item), item)
        except Exception as exc:
            reason = str(exc)
            unavailable.append((item, reason))
            write_event("Error", "ModelRegistry", "MODEL_LOAD_FAILED", f"{item['display_name']}: {reason}", model_id=item["model_id"])
    if not loaded and not unavailable:
        raise RuntimeError("No models are enabled. Install trained models and run scripts/install_trained_models.py")
    return ModelLoadResult(loaded=loaded, unavailable=unavailable)

"""Display the persisted Phase 6-9 model comparison without retraining."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    report = PROJECT_ROOT / "reports" / "model_evaluation" / "model_comparison.csv"
    selected = PROJECT_ROOT / "models" / "metadata" / "selected_model.json"
    if not report.exists() or not selected.exists():
        print("MODEL EVALUATION NOT FOUND; RUN train_models.py")
        return 1
    import pandas as pd

    print(pd.read_csv(report).to_string(index=False))
    print(f"selected_model={json.loads(selected.read_text(encoding='utf-8'))['model_id']}")
    print("MODEL EVALUATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

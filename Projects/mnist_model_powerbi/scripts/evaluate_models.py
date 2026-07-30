from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tensorflow as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.model_registry import load_models


def _probabilities(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    row_sums = values.sum(axis=1, keepdims=True)
    if np.all(values >= 0) and np.allclose(row_sums, 1.0, atol=1e-4):
        return values
    shifted = values - values.max(axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / exponentials.sum(axis=1, keepdims=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate every enabled model on the canonical MNIST test set."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=0,
        help="Number of test images to use; 0 evaluates all 10,000 images.",
    )
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "models" / "metadata" / "evaluation_summary.json",
    )
    args = parser.parse_args()

    (_, _), (images, labels) = tf.keras.datasets.mnist.load_data()
    if args.samples:
        if args.samples < 10 or args.samples > len(images):
            raise SystemExit(f"--samples must be between 10 and {len(images)}")
        images = images[: args.samples]
        labels = labels[: args.samples]

    inputs = images.astype(np.float32).reshape(-1, 28, 28, 1)
    loaded = load_models()
    results: list[dict] = []

    for key, (adapter, cfg) in loaded.loaded.items():
        model_inputs = adapter._adapt_input(inputs)
        started = time.perf_counter()
        output = np.asarray(
            adapter.model.predict(model_inputs, batch_size=args.batch_size, verbose=0)
        )
        elapsed = time.perf_counter() - started
        probs = _probabilities(output)
        predicted = np.argmax(probs, axis=1)
        correct = predicted == labels
        per_class = {
            str(digit): float(correct[labels == digit].mean())
            for digit in range(10)
        }
        results.append(
            {
                "model_key": key,
                "model_name": cfg["display_name"],
                "samples": int(len(labels)),
                "correct": int(correct.sum()),
                "test_accuracy": float(correct.mean()),
                "average_confidence": float(np.max(probs, axis=1).mean()),
                "evaluation_seconds": round(elapsed, 3),
                "per_class_accuracy": per_class,
                "configured_test_accuracy_before_evaluation": cfg.get("test_accuracy"),
            }
        )
        print(
            f"{cfg['display_name']}: {correct.mean():.4%} "
            f"({correct.sum()}/{len(labels)}) in {elapsed:.1f}s",
            flush=True,
        )

    results.sort(key=lambda item: (-item["test_accuracy"], item["model_name"]))
    summary = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "MNIST canonical test split",
        "sample_count": int(len(labels)),
        "input_range": "0..255 (normalization is inside the saved Keras models)",
        "successful_models": results,
        "failed_models": [
            {"model": cfg["display_name"], "reason": reason}
            for cfg, reason in loaded.unavailable
        ],
        "ranking": [item["model_name"] for item in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {args.output.resolve()}", flush=True)

    if loaded.unavailable:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

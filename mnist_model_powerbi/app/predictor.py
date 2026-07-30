from __future__ import annotations
from datetime import datetime
from pathlib import Path
import time
import numpy as np

from .config import PROCESSED_DIR
from .database import insert_prediction_batch
from .model_loader import ModelBundle
from .preprocessing import preprocess_image

def infer_actual_digit(filename: str) -> int | None:
    digits = [c for c in Path(filename).stem if c.isdigit()]
    return int(digits[0]) if len(digits) == 1 else None

def _result(model_name: str, probabilities: np.ndarray) -> dict:
    order = np.argsort(probabilities)[::-1]
    first, second = int(order[0]), int(order[1])
    result = {
        "ModelName": model_name,
        "PredictedDigit": first,
        "Confidence": float(probabilities[first]),
        "ConfidencePercentage": float(probabilities[first] * 100),
        "SecondPrediction": second,
        "SecondConfidence": float(probabilities[second]),
        "SecondConfidencePercentage": float(probabilities[second] * 100),
    }
    for i in range(10):
        result[f"ProbabilityDigit{i}"] = float(probabilities[i])
    return result

def predict_image(
    image_path: Path,
    models: ModelBundle,
    actual_digit: int | None = None,
) -> list[dict]:
    start = time.perf_counter()
    array, processed_image, original_size = preprocess_image(image_path)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / f"{image_path.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}_28x28.png"
    processed_image.save(output_path)

    nn_probs = models.neural_network.predict(array.reshape(1, 784), verbose=0)[0]
    cnn_probs = models.cnn.predict(array.reshape(1, 28, 28, 1), verbose=0)[0]

    elapsed_ms = (time.perf_counter() - start) * 1000
    prediction_time = datetime.now()

    predictions = [
        _result("Neural Network", nn_probs),
        _result("CNN", cnn_probs),
    ]

    for p in predictions:
        p.update({
            "ImageName": image_path.name,
            "OriginalImagePath": str(image_path.resolve()),
            "ProcessedImagePath": str(output_path.resolve()),
            "ActualDigit": actual_digit,
            "OriginalWidth": original_size[0],
            "OriginalHeight": original_size[1],
            "ProcessingTimeMilliseconds": elapsed_ms,
            "PredictionTime": prediction_time,
        })
        if actual_digit is None:
            p["CorrectPrediction"] = None
            p["PredictionStatus"] = "Not Labelled"
        else:
            p["CorrectPrediction"] = p["PredictedDigit"] == actual_digit
            p["PredictionStatus"] = "Correct" if p["CorrectPrediction"] else "Incorrect"

    batch_id = insert_prediction_batch(predictions)
    print(f"Saved batch {batch_id}")
    for p in predictions:
        print(f"{p['ModelName']}: {p['PredictedDigit']} ({p['ConfidencePercentage']:.2f}%)")
    return predictions

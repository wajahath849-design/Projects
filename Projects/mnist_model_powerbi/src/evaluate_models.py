from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from tensorflow import keras


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"
POWERBI_EXPORT_DIR = PROJECT_ROOT / "data" / "powerbi_exports"
RESULTS_DIR = PROJECT_ROOT / "reports" / "model_results"


def load_data() -> tuple:
    """Load test datasets for both model types."""

    x_test_nn = np.load(PROCESSED_DIR / "x_test_nn.npy")
    x_test_cnn = np.load(PROCESSED_DIR / "x_test_cnn.npy")
    y_test = np.load(PROCESSED_DIR / "y_test.npy")

    return x_test_nn, x_test_cnn, y_test


def evaluate_single_model(
    model_name: str,
    model_path: Path,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> dict:
    """Evaluate one model and prepare detailed analytical tables."""

    print(f"\nLoading {model_name} model...")

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found: {model_path}\n"
            "Train the model before running evaluation."
        )

    model = keras.models.load_model(model_path)

    print(f"Generating predictions for {model_name}...")

    probability_predictions = model.predict(
        x_test,
        batch_size=256,
        verbose=1,
    )

    predicted_classes = np.argmax(
        probability_predictions,
        axis=1,
    )

    confidence_scores = np.max(
        probability_predictions,
        axis=1,
    )

    correct_predictions = predicted_classes == y_test

    overall_accuracy = accuracy_score(
        y_test,
        predicted_classes,
    )

    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            y_test,
            predicted_classes,
            average="weighted",
            zero_division=0,
        )
    )

    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            y_test,
            predicted_classes,
            average="macro",
            zero_division=0,
        )
    )

    predictions_df = pd.DataFrame(
        {
            "Model": model_name,
            "ImageID": np.arange(len(y_test)),
            "ActualDigit": y_test,
            "PredictedDigit": predicted_classes,
            "Confidence": confidence_scores,
            "CorrectPrediction": correct_predictions,
            "PredictionStatus": np.where(
                correct_predictions,
                "Correct",
                "Incorrect",
            ),
        }
    )

    predictions_df["ConfidencePercentage"] = (
        predictions_df["Confidence"] * 100
    )

    predictions_df["DigitPair"] = (
        predictions_df["ActualDigit"].astype(str)
        + " → "
        + predictions_df["PredictedDigit"].astype(str)
    )

    confusion = confusion_matrix(
        y_test,
        predicted_classes,
        labels=list(range(10)),
    )

    confusion_records = []

    for actual_digit in range(10):
        for predicted_digit in range(10):
            confusion_records.append(
                {
                    "Model": model_name,
                    "ActualDigit": actual_digit,
                    "PredictedDigit": predicted_digit,
                    "PredictionCount": int(
                        confusion[actual_digit, predicted_digit]
                    ),
                    "CorrectCell": (
                        actual_digit == predicted_digit
                    ),
                }
            )

    confusion_df = pd.DataFrame(confusion_records)

    class_precision, class_recall, class_f1, class_support = (
        precision_recall_fscore_support(
            y_test,
            predicted_classes,
            labels=list(range(10)),
            zero_division=0,
        )
    )

    digit_records = []

    for digit in range(10):
        digit_mask = y_test == digit
        digit_total = int(np.sum(digit_mask))

        digit_correct = int(
            np.sum(
                predicted_classes[digit_mask]
                == y_test[digit_mask]
            )
        )

        digit_incorrect = digit_total - digit_correct

        digit_accuracy = (
            digit_correct / digit_total
            if digit_total > 0
            else 0
        )

        digit_confidence = float(
            np.mean(confidence_scores[digit_mask])
        )

        digit_records.append(
            {
                "Model": model_name,
                "Digit": digit,
                "Precision": float(class_precision[digit]),
                "Recall": float(class_recall[digit]),
                "F1Score": float(class_f1[digit]),
                "Support": int(class_support[digit]),
                "CorrectPredictions": digit_correct,
                "IncorrectPredictions": digit_incorrect,
                "DigitAccuracy": float(digit_accuracy),
                "AverageConfidence": digit_confidence,
            }
        )

    digit_performance_df = pd.DataFrame(digit_records)

    report = classification_report(
        y_test,
        predicted_classes,
        output_dict=True,
        zero_division=0,
    )

    evaluation_summary = {
        "Model": model_name,
        "Accuracy": float(overall_accuracy),
        "WeightedPrecision": float(weighted_precision),
        "WeightedRecall": float(weighted_recall),
        "WeightedF1Score": float(weighted_f1),
        "MacroPrecision": float(macro_precision),
        "MacroRecall": float(macro_recall),
        "MacroF1Score": float(macro_f1),
        "TotalPredictions": int(len(y_test)),
        "CorrectPredictions": int(
            np.sum(correct_predictions)
        ),
        "IncorrectPredictions": int(
            np.sum(~correct_predictions)
        ),
        "AverageConfidence": float(
            np.mean(confidence_scores)
        ),
    }

    return {
        "summary": evaluation_summary,
        "predictions": predictions_df,
        "confusion": confusion_df,
        "digit_performance": digit_performance_df,
        "classification_report": report,
    }


def evaluate_models() -> None:
    """Evaluate Neural Network and CNN models."""

    POWERBI_EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    x_test_nn, x_test_cnn, y_test = load_data()

    neural_network_results = evaluate_single_model(
        model_name="Neural Network",
        model_path=MODEL_DIR / "neural_network.keras",
        x_test=x_test_nn,
        y_test=y_test,
    )

    cnn_model_path = MODEL_DIR / "cnn_best.keras"

    if not cnn_model_path.exists():
        cnn_model_path = MODEL_DIR / "cnn.keras"

    cnn_results = evaluate_single_model(
        model_name="CNN",
        model_path=cnn_model_path,
        x_test=x_test_cnn,
        y_test=y_test,
    )

    combined_summary = pd.DataFrame(
        [
            neural_network_results["summary"],
            cnn_results["summary"],
        ]
    )

    combined_predictions = pd.concat(
        [
            neural_network_results["predictions"],
            cnn_results["predictions"],
        ],
        ignore_index=True,
    )

    combined_confusion = pd.concat(
        [
            neural_network_results["confusion"],
            cnn_results["confusion"],
        ],
        ignore_index=True,
    )

    combined_digit_performance = pd.concat(
        [
            neural_network_results["digit_performance"],
            cnn_results["digit_performance"],
        ],
        ignore_index=True,
    )

    incorrect_predictions = combined_predictions[
        combined_predictions["CorrectPrediction"] == False
    ].copy()

    incorrect_predictions.sort_values(
        by="Confidence",
        ascending=False,
        inplace=True,
    )

    model_comparison = combined_summary.copy()

    best_accuracy = model_comparison[
        "Accuracy"
    ].max()

    model_comparison["AccuracyRank"] = (
        model_comparison["Accuracy"]
        .rank(
            method="dense",
            ascending=False,
        )
        .astype(int)
    )

    model_comparison["AccuracyDifferenceFromBest"] = (
        best_accuracy - model_comparison["Accuracy"]
    )

    model_comparison["AccuracyPercentage"] = (
        model_comparison["Accuracy"] * 100
    )

    model_comparison["WeightedF1Percentage"] = (
        model_comparison["WeightedF1Score"] * 100
    )

    model_comparison["ErrorRate"] = (
        1 - model_comparison["Accuracy"]
    )

    combined_summary.to_csv(
        POWERBI_EXPORT_DIR / "evaluation_summary.csv",
        index=False,
    )

    combined_predictions.to_csv(
        POWERBI_EXPORT_DIR / "predictions.csv",
        index=False,
    )

    combined_confusion.to_csv(
        POWERBI_EXPORT_DIR / "confusion_matrix.csv",
        index=False,
    )

    combined_digit_performance.to_csv(
        POWERBI_EXPORT_DIR / "digit_performance.csv",
        index=False,
    )

    incorrect_predictions.to_csv(
        POWERBI_EXPORT_DIR / "incorrect_predictions.csv",
        index=False,
    )

    model_comparison.to_csv(
        POWERBI_EXPORT_DIR / "model_comparison.csv",
        index=False,
    )

    with open(
        RESULTS_DIR / "neural_network_classification_report.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            neural_network_results[
                "classification_report"
            ],
            file,
            indent=4,
        )

    with open(
        RESULTS_DIR / "cnn_classification_report.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            cnn_results["classification_report"],
            file,
            indent=4,
        )

    print("\nEvaluation completed successfully.")

    print("\nModel comparison:")
    print(
        model_comparison[
            [
                "Model",
                "Accuracy",
                "WeightedPrecision",
                "WeightedRecall",
                "WeightedF1Score",
                "CorrectPredictions",
                "IncorrectPredictions",
            ]
        ].to_string(index=False)
    )

    print(
        f"\nPower BI files saved in: "
        f"{POWERBI_EXPORT_DIR}"
    )


if __name__ == "__main__":
    evaluate_models()
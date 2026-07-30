from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
POWERBI_EXPORT_DIR = PROJECT_ROOT / "data" / "powerbi_exports"


def read_required_csv(filename: str) -> pd.DataFrame:
    """Read a required CSV file and raise a clear error if missing."""

    file_path = POWERBI_EXPORT_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}\n"
            "Run the previous training and evaluation steps first."
        )

    return pd.read_csv(file_path)


def create_training_history_table() -> pd.DataFrame:
    """Combine Neural Network and CNN training history."""

    neural_network_history = read_required_csv(
        "neural_network_training_history.csv"
    )
    cnn_history = read_required_csv(
        "cnn_training_history.csv"
    )

    combined_history = pd.concat(
        [neural_network_history, cnn_history],
        ignore_index=True,
    )

    required_columns = [
        "Model",
        "Epoch",
        "TrainingAccuracy",
        "ValidationAccuracy",
        "TrainingLoss",
        "ValidationLoss",
    ]

    for column in required_columns:
        if column not in combined_history.columns:
            raise ValueError(
                f"Missing column '{column}' in training-history files."
            )

    combined_history["TrainingAccuracyPercentage"] = (
        combined_history["TrainingAccuracy"] * 100
    )

    combined_history["ValidationAccuracyPercentage"] = (
        combined_history["ValidationAccuracy"] * 100
    )

    combined_history["AccuracyGap"] = (
        combined_history["TrainingAccuracy"]
        - combined_history["ValidationAccuracy"]
    )

    combined_history["AccuracyGapPercentage"] = (
        combined_history["AccuracyGap"] * 100
    )

    combined_history["LossGap"] = (
        combined_history["ValidationLoss"]
        - combined_history["TrainingLoss"]
    )

    combined_history["OverfittingIndicator"] = combined_history[
        "AccuracyGapPercentage"
    ].apply(
        lambda value: (
            "Possible Overfitting"
            if value > 2
            else "Normal"
        )
    )

    combined_history.sort_values(
        by=["Model", "Epoch"],
        inplace=True,
    )

    combined_history.to_csv(
        POWERBI_EXPORT_DIR / "training_history.csv",
        index=False,
    )

    return combined_history


def create_model_summary_table() -> pd.DataFrame:
    """Combine training details and final evaluation metrics."""

    neural_network_summary = read_required_csv(
        "neural_network_summary.csv"
    )
    cnn_summary = read_required_csv(
        "cnn_summary.csv"
    )
    evaluation_summary = read_required_csv(
        "evaluation_summary.csv"
    )

    training_summary = pd.concat(
        [neural_network_summary, cnn_summary],
        ignore_index=True,
    )

    final_summary = training_summary.merge(
        evaluation_summary,
        on="Model",
        how="left",
    )

    final_summary["TestAccuracyPercentage"] = (
        final_summary["TestAccuracy"] * 100
    )

    final_summary["EvaluationAccuracyPercentage"] = (
        final_summary["Accuracy"] * 100
    )

    final_summary["WeightedPrecisionPercentage"] = (
        final_summary["WeightedPrecision"] * 100
    )

    final_summary["WeightedRecallPercentage"] = (
        final_summary["WeightedRecall"] * 100
    )

    final_summary["WeightedF1Percentage"] = (
        final_summary["WeightedF1Score"] * 100
    )

    final_summary["AverageConfidencePercentage"] = (
        final_summary["AverageConfidence"] * 100
    )

    final_summary["ErrorRate"] = (
        1 - final_summary["Accuracy"]
    )

    final_summary["ErrorRatePercentage"] = (
        final_summary["ErrorRate"] * 100
    )

    final_summary["PredictionsPerSecond"] = (
        final_summary["TotalPredictions"]
        / final_summary["TrainingTimeSeconds"]
    )

    best_accuracy = final_summary["Accuracy"].max()

    final_summary["AccuracyDifferenceFromBest"] = (
        best_accuracy - final_summary["Accuracy"]
    )

    final_summary["AccuracyDifferenceFromBestPercentage"] = (
        final_summary["AccuracyDifferenceFromBest"] * 100
    )

    final_summary["AccuracyRank"] = (
        final_summary["Accuracy"]
        .rank(
            method="dense",
            ascending=False,
        )
        .astype(int)
    )

    final_summary["ModelResult"] = final_summary[
        "AccuracyRank"
    ].apply(
        lambda rank: (
            "Best Model"
            if rank == 1
            else "Comparison Model"
        )
    )

    final_summary.to_csv(
        POWERBI_EXPORT_DIR / "final_model_summary.csv",
        index=False,
    )

    return final_summary


def create_digit_comparison_table() -> pd.DataFrame:
    """Create side-by-side digit performance comparison."""

    digit_performance = read_required_csv(
        "digit_performance.csv"
    )

    digit_performance["AccuracyPercentage"] = (
        digit_performance["DigitAccuracy"] * 100
    )

    digit_performance["PrecisionPercentage"] = (
        digit_performance["Precision"] * 100
    )

    digit_performance["RecallPercentage"] = (
        digit_performance["Recall"] * 100
    )

    digit_performance["F1Percentage"] = (
        digit_performance["F1Score"] * 100
    )

    digit_performance["AverageConfidencePercentage"] = (
        digit_performance["AverageConfidence"] * 100
    )

    digit_performance["ErrorRate"] = (
        1 - digit_performance["DigitAccuracy"]
    )

    digit_performance["ErrorRatePercentage"] = (
        digit_performance["ErrorRate"] * 100
    )

    digit_performance["DifficultyLevel"] = pd.cut(
        digit_performance["AccuracyPercentage"],
        bins=[0, 95, 98, 100],
        labels=[
            "Difficult",
            "Moderate",
            "Easy",
        ],
        include_lowest=True,
    )

    digit_performance.to_csv(
        POWERBI_EXPORT_DIR / "digit_model_comparison.csv",
        index=False,
    )

    return digit_performance


def create_error_analysis_table() -> pd.DataFrame:
    """Enhance incorrect-prediction data for Power BI analysis."""

    incorrect_predictions = read_required_csv(
        "incorrect_predictions.csv"
    )

    incorrect_predictions["ConfidenceBand"] = pd.cut(
        incorrect_predictions["ConfidencePercentage"],
        bins=[0, 50, 70, 90, 100],
        labels=[
            "Low Confidence",
            "Medium Confidence",
            "High Confidence",
            "Very High Confidence",
        ],
        include_lowest=True,
    )

    incorrect_predictions["ErrorType"] = (
        incorrect_predictions["ActualDigit"].astype(str)
        + " misclassified as "
        + incorrect_predictions["PredictedDigit"].astype(str)
    )

    incorrect_predictions["ConfidenceRankWithinModel"] = (
        incorrect_predictions.groupby("Model")[
            "Confidence"
        ]
        .rank(
            method="dense",
            ascending=False,
        )
        .astype(int)
    )

    incorrect_predictions["HighConfidenceError"] = (
        incorrect_predictions["ConfidencePercentage"] >= 90
    )

    incorrect_predictions.to_csv(
        POWERBI_EXPORT_DIR / "error_analysis.csv",
        index=False,
    )

    return incorrect_predictions


def export_powerbi_data() -> None:
    """Create final cleaned tables for Power BI."""

    POWERBI_EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Creating combined training-history table...")
    training_history = create_training_history_table()

    print("Creating final model-summary table...")
    model_summary = create_model_summary_table()

    print("Creating digit comparison table...")
    digit_comparison = create_digit_comparison_table()

    print("Creating error-analysis table...")
    error_analysis = create_error_analysis_table()

    print("\nPower BI export preparation completed successfully.")

    print("\nGenerated final tables:")
    print(
        f"training_history.csv: "
        f"{len(training_history):,} rows"
    )
    print(
        f"final_model_summary.csv: "
        f"{len(model_summary):,} rows"
    )
    print(
        f"digit_model_comparison.csv: "
        f"{len(digit_comparison):,} rows"
    )
    print(
        f"error_analysis.csv: "
        f"{len(error_analysis):,} rows"
    )

    print(
        f"\nFiles saved in: "
        f"{POWERBI_EXPORT_DIR}"
    )


if __name__ == "__main__":
    export_powerbi_data()
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps
from tensorflow import keras

from database import insert_prediction_batch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models"
PROCESSED_IMAGE_DIR = (
    PROJECT_ROOT
    / "reports"
    / "figures"
    / "custom_predictions"
)

SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
}


def detect_and_normalize_background(
    image_array: np.ndarray,
) -> np.ndarray:
    """
    Convert the image to MNIST style:
    black background and bright handwritten digit.
    """

    border_pixels = np.concatenate(
        [
            image_array[0, :],
            image_array[-1, :],
            image_array[:, 0],
            image_array[:, -1],
        ]
    )

    border_average = float(
        np.mean(border_pixels)
    )

    # White paper or bright background.
    if border_average > 127:
        image_array = 255 - image_array

    return image_array


def improve_contrast(
    image_array: np.ndarray,
) -> np.ndarray:
    """Normalize contrast and suppress weak background noise."""

    working_array = image_array.astype(
        np.float32
    )

    minimum_value = float(
        np.min(working_array)
    )
    maximum_value = float(
        np.max(working_array)
    )

    if maximum_value > minimum_value:
        working_array = (
            (
                working_array
                - minimum_value
            )
            / (
                maximum_value
                - minimum_value
            )
            * 255
        )

    working_array[
        working_array < 25
    ] = 0

    return working_array.astype(
        np.uint8
    )


def crop_digit(
    image: Image.Image,
) -> Image.Image:
    """Crop the visible handwritten digit from the image."""

    image_array = np.asarray(
        image
    )

    digit_positions = np.argwhere(
        image_array > 20
    )

    if digit_positions.size == 0:
        raise ValueError(
            "No handwritten digit was detected."
        )

    top, left = digit_positions.min(
        axis=0
    )
    bottom, right = digit_positions.max(
        axis=0
    )

    margin = 4

    left = max(
        0,
        int(left) - margin,
    )
    top = max(
        0,
        int(top) - margin,
    )
    right = min(
        image.width - 1,
        int(right) + margin,
    )
    bottom = min(
        image.height - 1,
        int(bottom) + margin,
    )

    return image.crop(
        (
            left,
            top,
            right + 1,
            bottom + 1,
        )
    )


def resize_and_center_digit(
    image: Image.Image,
) -> Image.Image:
    """
    Resize the digit proportionally and place it
    inside a 28x28 MNIST-style canvas.
    """

    target_digit_size = 20

    width, height = image.size

    if width <= 0 or height <= 0:
        raise ValueError(
            "The cropped image has invalid dimensions."
        )

    scale = min(
        target_digit_size / width,
        target_digit_size / height,
    )

    resized_width = max(
        1,
        round(width * scale),
    )
    resized_height = max(
        1,
        round(height * scale),
    )

    resized_digit = image.resize(
        (
            resized_width,
            resized_height,
        ),
        Image.Resampling.LANCZOS,
    )

    canvas = Image.new(
        mode="L",
        size=(28, 28),
        color=0,
    )

    left_position = (
        28 - resized_width
    ) // 2

    top_position = (
        28 - resized_height
    ) // 2

    canvas.paste(
        resized_digit,
        (
            left_position,
            top_position,
        ),
    )

    return canvas


def preprocess_custom_image(
    image_path: Path,
) -> tuple[
    np.ndarray,
    Image.Image,
    tuple[int, int],
]:
    """
    Convert a custom image into a normalized 28x28 image.
    """

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    if (
        image_path.suffix.lower()
        not in SUPPORTED_EXTENSIONS
    ):
        raise ValueError(
            "Unsupported image format. "
            "Use PNG, JPG, JPEG, or BMP."
        )

    original_image = Image.open(
        image_path
    )

    original_image = (
        ImageOps.exif_transpose(
            original_image
        )
    )

    original_width, original_height = (
        original_image.size
    )

    grayscale_image = (
        original_image.convert("L")
    )

    image_array = np.asarray(
        grayscale_image
    )

    image_array = (
        detect_and_normalize_background(
            image_array
        )
    )

    image_array = improve_contrast(
        image_array
    )

    normalized_image = Image.fromarray(
        image_array,
        mode="L",
    )

    cropped_image = crop_digit(
        normalized_image
    )

    processed_image = (
        resize_and_center_digit(
            cropped_image
        )
    )

    processed_array = np.asarray(
        processed_image,
        dtype=np.float32,
    )

    processed_array = (
        processed_array / 255.0
    )

    return (
        processed_array,
        processed_image,
        (
            original_width,
            original_height,
        ),
    )


def load_models() -> tuple[
    keras.Model,
    keras.Model,
]:
    """Load the trained Neural Network and CNN models."""

    neural_network_path = (
        MODEL_DIR
        / "neural_network.keras"
    )

    cnn_model_path = (
        MODEL_DIR
        / "cnn_best.keras"
    )

    if not cnn_model_path.exists():
        cnn_model_path = (
            MODEL_DIR
            / "cnn.keras"
        )

    if not neural_network_path.exists():
        raise FileNotFoundError(
            "Neural Network model not found. "
            "Run train_neural_network.py first."
        )

    if not cnn_model_path.exists():
        raise FileNotFoundError(
            "CNN model not found. "
            "Run train_cnn.py first."
        )

    neural_network = (
        keras.models.load_model(
            neural_network_path
        )
    )

    cnn_model = (
        keras.models.load_model(
            cnn_model_path
        )
    )

    return (
        neural_network,
        cnn_model,
    )


def create_prediction_result(
    model_name: str,
    probabilities: np.ndarray,
) -> dict[str, Any]:
    """Convert model probabilities into a structured result."""

    predicted_digit = int(
        np.argmax(probabilities)
    )

    confidence = float(
        probabilities[
            predicted_digit
        ]
    )

    ordered_indices = np.argsort(
        probabilities
    )[::-1]

    second_prediction = int(
        ordered_indices[1]
    )

    second_confidence = float(
        probabilities[
            second_prediction
        ]
    )

    result: dict[str, Any] = {
        "Model": model_name,
        "PredictedDigit": predicted_digit,
        "Confidence": confidence,
        "ConfidencePercentage": (
            confidence * 100
        ),
        "SecondPrediction": (
            second_prediction
        ),
        "SecondConfidence": (
            second_confidence
        ),
        "SecondConfidencePercentage": (
            second_confidence * 100
        ),
    }

    for digit in range(10):
        result[
            f"ProbabilityDigit{digit}"
        ] = float(
            probabilities[digit]
        )

    return result


def predict_with_models(
    processed_array: np.ndarray,
    neural_network: keras.Model,
    cnn_model: keras.Model,
) -> list[dict[str, Any]]:
    """Generate predictions using both trained models."""

    neural_network_input = (
        processed_array.reshape(
            1,
            784,
        )
    )

    cnn_input = processed_array.reshape(
        1,
        28,
        28,
        1,
    )

    neural_network_probabilities = (
        neural_network.predict(
            neural_network_input,
            verbose=0,
        )[0]
    )

    cnn_probabilities = (
        cnn_model.predict(
            cnn_input,
            verbose=0,
        )[0]
    )

    return [
        create_prediction_result(
            model_name="Neural Network",
            probabilities=(
                neural_network_probabilities
            ),
        ),
        create_prediction_result(
            model_name="CNN",
            probabilities=(
                cnn_probabilities
            ),
        ),
    ]


def enrich_predictions(
    predictions: list[dict[str, Any]],
    image_path: Path,
    processed_image_path: Path,
    original_size: tuple[int, int],
    actual_digit: int | None,
) -> None:
    """Add image metadata and validation fields."""

    prediction_time = datetime.now()

    original_width, original_height = (
        original_size
    )

    for prediction in predictions:
        prediction["ImageName"] = (
            image_path.name
        )

        prediction[
            "OriginalImagePath"
        ] = str(
            image_path.resolve()
        )

        prediction[
            "ProcessedImagePath"
        ] = str(
            processed_image_path.resolve()
        )

        prediction["OriginalWidth"] = (
            original_width
        )

        prediction["OriginalHeight"] = (
            original_height
        )

        prediction["ProcessedWidth"] = 28
        prediction["ProcessedHeight"] = 28
        prediction["PredictionTime"] = (
            prediction_time
        )
        prediction["ActualDigit"] = (
            actual_digit
        )

        if actual_digit is None:
            prediction[
                "CorrectPrediction"
            ] = None

            prediction[
                "PredictionStatus"
            ] = "Not Labelled"

        else:
            is_correct = (
                prediction[
                    "PredictedDigit"
                ]
                == actual_digit
            )

            prediction[
                "CorrectPrediction"
            ] = is_correct

            prediction[
                "PredictionStatus"
            ] = (
                "Correct"
                if is_correct
                else "Incorrect"
            )


def print_results(
    predictions: list[dict[str, Any]],
    actual_digit: int | None,
) -> None:
    """Print readable prediction results."""

    print(
        "\nCustom image prediction results:"
    )

    for prediction in predictions:
        print(
            f"\n{prediction['Model']}"
        )
        print(
            "Predicted digit: "
            f"{prediction['PredictedDigit']}"
        )
        print(
            "Confidence: "
            f"{prediction['ConfidencePercentage']:.2f}%"
        )
        print(
            "Second choice: "
            f"{prediction['SecondPrediction']} "
            f"({prediction['SecondConfidencePercentage']:.2f}%)"
        )

        if actual_digit is not None:
            print(
                f"Actual digit: {actual_digit}"
            )
            print(
                "Result: "
                f"{prediction['PredictionStatus']}"
            )


def predict_custom_image(
    image_path: Path,
    actual_digit: int | None = None,
    neural_network: keras.Model | None = None,
    cnn_model: keras.Model | None = None,
) -> list[dict[str, Any]]:
    """
    Process one handwritten image, predict it with both
    models, and save the results to SQL Server.
    """

    if (
        actual_digit is not None
        and actual_digit not in range(10)
    ):
        raise ValueError(
            "Actual digit must be between 0 and 9."
        )

    PROCESSED_IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        processed_array,
        processed_image,
        original_size,
    ) = preprocess_custom_image(
        image_path
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    processed_image_path = (
        PROCESSED_IMAGE_DIR
        / (
            f"{image_path.stem}_"
            f"{timestamp}_28x28.png"
        )
    )

    processed_image.save(
        processed_image_path
    )

    if (
        neural_network is None
        or cnn_model is None
    ):
        (
            neural_network,
            cnn_model,
        ) = load_models()

    predictions = predict_with_models(
        processed_array=processed_array,
        neural_network=neural_network,
        cnn_model=cnn_model,
    )

    enrich_predictions(
        predictions=predictions,
        image_path=image_path,
        processed_image_path=(
            processed_image_path
        ),
        original_size=original_size,
        actual_digit=actual_digit,
    )

    batch_id = insert_prediction_batch(
        predictions
    )

    print_results(
        predictions=predictions,
        actual_digit=actual_digit,
    )

    print(
        "\nProcessed 28x28 image:"
    )
    print(
        processed_image_path.resolve()
    )

    print(
        "\nSQL prediction batch:"
    )
    print(batch_id)

    return predictions


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Predict a handwritten digit "
            "using the trained MNIST models."
        )
    )

    parser.add_argument(
        "image",
        type=Path,
        help=(
            "Path to a PNG, JPG, JPEG, "
            "or BMP image."
        ),
    )

    parser.add_argument(
        "--actual",
        type=int,
        choices=range(10),
        default=None,
        help=(
            "Optional correct digit "
            "from 0 to 9."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()

    predict_custom_image(
        image_path=arguments.image,
        actual_digit=arguments.actual,
    )
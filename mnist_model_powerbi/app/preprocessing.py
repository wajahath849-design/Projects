from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .config import SUPPORTED_EXTENSIONS


def _load_grayscale(image_path: Path) -> tuple[np.ndarray, tuple[int, int]]:
    """Load an image, apply EXIF rotation, and return grayscale pixels."""

    original = ImageOps.exif_transpose(Image.open(image_path))
    original_size = original.size
    grayscale = np.asarray(original.convert("L"), dtype=np.uint8)

    return grayscale, original_size


def _normalize_lighting(gray: np.ndarray) -> np.ndarray:
    """Reduce uneven lighting and improve local contrast."""

    blurred_background = cv2.GaussianBlur(
        gray,
        (0, 0),
        sigmaX=15,
        sigmaY=15,
    )

    normalized = cv2.divide(
        gray,
        blurred_background,
        scale=255,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    return clahe.apply(normalized)


def _create_binary_digit(gray: np.ndarray) -> np.ndarray:
    """
    Produce a white digit on a black background.

    Adaptive thresholding handles shadows and uneven phone-camera lighting.
    """

    denoised = cv2.GaussianBlur(
        gray,
        (5, 5),
        0,
    )

    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        12,
    )

    # Remove isolated noise while preserving the handwritten stroke.
    kernel = np.ones((2, 2), dtype=np.uint8)

    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        kernel,
        iterations=1,
    )

    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=1,
    )

    return binary


def _extract_largest_digit(binary: np.ndarray) -> np.ndarray:
    """Keep the largest meaningful connected contour."""

    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if not contours:
        raise ValueError(
            "No handwritten digit contour was detected."
        )

    image_area = binary.shape[0] * binary.shape[1]

    valid_contours = [
        contour
        for contour in contours
        if cv2.contourArea(contour) >= max(20, image_area * 0.0005)
    ]

    if not valid_contours:
        raise ValueError(
            "No sufficiently large handwritten digit was detected."
        )

    largest_contour = max(
        valid_contours,
        key=cv2.contourArea,
    )

    x, y, width, height = cv2.boundingRect(
        largest_contour
    )

    margin = max(
        4,
        round(max(width, height) * 0.12),
    )

    left = max(0, x - margin)
    top = max(0, y - margin)
    right = min(binary.shape[1], x + width + margin)
    bottom = min(binary.shape[0], y + height + margin)

    cropped = binary[
        top:bottom,
        left:right,
    ]

    if cropped.size == 0:
        raise ValueError(
            "The detected digit crop is empty."
        )

    return cropped


def _deskew_digit(digit: np.ndarray) -> np.ndarray:
    """Deskew the digit using image moments, similar to MNIST preparation."""

    moments = cv2.moments(digit)

    if abs(moments["mu02"]) < 1e-2:
        return digit

    skew = moments["mu11"] / moments["mu02"]

    transform = np.float32(
        [
            [1, skew, -0.5 * digit.shape[0] * skew],
            [0, 1, 0],
        ]
    )

    deskewed = cv2.warpAffine(
        digit,
        transform,
        (digit.shape[1], digit.shape[0]),
        flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    return deskewed


def _resize_to_mnist_box(digit: np.ndarray) -> np.ndarray:
    """Resize proportionally so the digit fits inside a 20×20 region."""

    height, width = digit.shape

    if width <= 0 or height <= 0:
        raise ValueError(
            "The extracted digit has invalid dimensions."
        )

    target = 20
    scale = min(
        target / width,
        target / height,
    )

    new_width = max(
        1,
        round(width * scale),
    )
    new_height = max(
        1,
        round(height * scale),
    )

    interpolation = (
        cv2.INTER_AREA
        if scale < 1
        else cv2.INTER_CUBIC
    )

    return cv2.resize(
        digit,
        (new_width, new_height),
        interpolation=interpolation,
    )


def _center_by_mass(digit: np.ndarray) -> np.ndarray:
    """Place the digit on a 28×28 canvas and align its centre of mass."""

    canvas = np.zeros(
        (28, 28),
        dtype=np.uint8,
    )

    height, width = digit.shape

    x = (28 - width) // 2
    y = (28 - height) // 2

    canvas[
        y:y + height,
        x:x + width,
    ] = digit

    moments = cv2.moments(canvas)

    if moments["m00"] == 0:
        return canvas

    center_x = moments["m10"] / moments["m00"]
    center_y = moments["m01"] / moments["m00"]

    shift_x = round(13.5 - center_x)
    shift_y = round(13.5 - center_y)

    transform = np.float32(
        [
            [1, 0, shift_x],
            [0, 1, shift_y],
        ]
    )

    centered = cv2.warpAffine(
        canvas,
        transform,
        (28, 28),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    return centered


def preprocess_image(
    image_path: Path,
) -> tuple[np.ndarray, Image.Image, tuple[int, int]]:
    """
    Convert a phone photo or scanned handwritten digit to MNIST format.

    Processing stages:
    1. EXIF orientation and grayscale conversion.
    2. Lighting normalization and local contrast enhancement.
    3. Adaptive thresholding.
    4. Noise cleanup.
    5. Largest-contour extraction.
    6. Deskewing.
    7. Proportional resize into a 20×20 box.
    8. Centre-of-mass alignment on a 28×28 canvas.
    """

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image extension: {image_path.suffix}"
        )

    grayscale, original_size = _load_grayscale(
        image_path
    )

    normalized_lighting = _normalize_lighting(
        grayscale
    )

    binary = _create_binary_digit(
        normalized_lighting
    )

    cropped = _extract_largest_digit(
        binary
    )

    deskewed = _deskew_digit(
        cropped
    )

    resized = _resize_to_mnist_box(
        deskewed
    )

    centered = _center_by_mass(
        resized
    )

    processed_image = Image.fromarray(
        centered,
        mode="L",
    )

    normalized_array = (
        centered.astype(np.float32)
        / 255.0
    )

    return (
        normalized_array,
        processed_image,
        original_size,
    )

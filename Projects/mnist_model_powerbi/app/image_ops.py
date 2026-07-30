from __future__ import annotations

import hashlib
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .preprocessing.generic import _mnist_canvas


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def actual_class_from_filename(filename: str) -> str | None:
    """Read an optional MNIST ground-truth label from conservative filename patterns."""
    stem = Path(filename).stem.lower()
    patterns = (
        r"^(?:digit|actual|label)[_-]?([0-9])(?:[_-].*)?$",
        r"^([0-9])(?:[_-].*)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, stem)
        if match:
            return match.group(1)
    return None


def image_quality(path: Path) -> tuple[int, int, float, float, float]:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        raise ValueError("Unsupported or unreadable image. Use PNG, JPG, JPEG, BMP or WEBP.")
    return (
        int(image.shape[1]),
        int(image.shape[0]),
        float(image.mean()),
        float(image.std()),
        float(cv2.Laplacian(image, cv2.CV_64F).var()),
    )


def save_display_png(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.save(target_path, format="PNG", optimize=True)


def save_processed_preview_png(
    source_path: Path,
    target_path: Path,
    width: int = 28,
    height: int = 28,
    preview_scale: int = 8,
) -> None:
    """Persist a pixel-perfect enlarged preview of the 28x28 classifier input."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        pixels = np.clip(_mnist_canvas(image, width, height) * 255.0, 0, 255).astype(np.uint8)
    preview = Image.fromarray(pixels, mode="L")
    if preview_scale > 1:
        preview = preview.resize(
            (width * preview_scale, height * preview_scale),
            resample=Image.Resampling.NEAREST,
        )
    preview.save(target_path, format="PNG", optimize=True)

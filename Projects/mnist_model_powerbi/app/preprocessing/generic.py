from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def _mnist_canvas(image: Image.Image, width: int, height: int) -> np.ndarray:
    image = ImageOps.exif_transpose(image).convert("L")
    array = np.asarray(image, dtype=np.uint8)

    # MNIST uses a light digit on a dark background. Invert ordinary paper scans.
    light_background = float(array.mean()) > 127.0
    if light_background:
        array = 255 - array

    # Preserve canonical MNIST tensors. Their native antialiasing and centering
    # are already the distribution on which the models were trained.
    if array.shape == (height, width) and not light_background:
        return array.astype(np.float32) / 255.0

    mask = array > 20
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("No visible digit was found in the image")

    margin = 2
    left = max(0, int(xs.min()) - margin)
    right = min(array.shape[1], int(xs.max()) + margin + 1)
    top = max(0, int(ys.min()) - margin)
    bottom = min(array.shape[0], int(ys.max()) + margin + 1)
    cropped = Image.fromarray(array[top:bottom, left:right])

    target_box = max(1, min(width, height) - 8)
    scale = min(target_box / cropped.width, target_box / cropped.height)
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )

    canvas = Image.new("L", (width, height), 0)
    canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    if light_background:
        # Uploaded paper photos contain low-level texture and weak antialiasing
        # that MNIST does not. Remove that noise and expand the stroke by one
        # pixel so the canvas better matches MNIST foreground density.
        canvas_array = np.asarray(canvas, dtype=np.uint8)
        canvas = Image.fromarray(np.where(canvas_array > 25, 255, 0).astype(np.uint8))
        canvas = canvas.filter(ImageFilter.MaxFilter(3))
    return np.asarray(canvas, dtype=np.float32) / 255.0


def load_image(path: str | Path, cfg: dict) -> np.ndarray:
    width, height = (int(v) for v in cfg.get("input_size", [28, 28]))
    channels = int(cfg.get("channels", 1))
    profile = str(cfg.get("preprocessing", "mnist")).lower()

    with Image.open(path) as image:
        if profile == "mnist":
            array = _mnist_canvas(image, width, height)
            if str(cfg.get("input_range", "0_1")).lower() in {"0_255", "raw_255"}:
                array = array * 255.0
            if channels == 1:
                return array.reshape(1, height, width, 1)
            rgb = np.repeat(array[..., None], 3, axis=-1)
            return rgb.reshape(1, height, width, 3)

        mode = "L" if channels == 1 else "RGB"
        fitted = ImageOps.fit(ImageOps.exif_transpose(image).convert(mode), (width, height), Image.Resampling.LANCZOS)
        array = np.asarray(fitted, dtype=np.float32) / 255.0
        if channels == 1:
            array = array[..., None]
        return np.expand_dims(array, axis=0)

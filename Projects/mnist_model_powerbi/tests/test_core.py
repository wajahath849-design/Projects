import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app import config
from app.image_ops import actual_class_from_filename
from app.model_registry import read_model_configs
from app.preprocessing.generic import load_image
from app.probability import normalise_probabilities


def test_actual_class_parser():
    assert actual_class_from_filename("digit_8.png") == "8"
    assert actual_class_from_filename("label-4-test.jpg") == "4"
    assert actual_class_from_filename("digit_10.jpg") is None
    assert actual_class_from_filename("holiday8.jpg") is None


def test_mnist_preprocessing(tmp_path: Path):
    path = tmp_path / "digit.png"
    image = Image.new("L", (80, 60), 255)
    draw = ImageDraw.Draw(image)
    draw.line((40, 10, 40, 50), fill=0, width=8)
    image.save(path)
    output = load_image(
        path,
        {"input_size": [28, 28], "channels": 1, "preprocessing": "mnist"},
    )
    assert output.shape == (1, 28, 28, 1)
    assert np.isfinite(output).all()
    assert 0 <= output.min() <= output.max() <= 1


def test_mnist_preprocessing_raw_pixel_range(tmp_path: Path):
    path = tmp_path / "digit.png"
    image = Image.new("L", (80, 60), 255)
    draw = ImageDraw.Draw(image)
    draw.line((40, 10, 40, 50), fill=0, width=8)
    image.save(path)
    output = load_image(
        path,
        {
            "input_size": [28, 28],
            "channels": 1,
            "preprocessing": "mnist",
            "input_range": "0_255",
        },
    )
    assert output.shape == (1, 28, 28, 1)
    assert set(np.unique(output)).issubset({0.0, 255.0})
    assert output.max() == 255.0


def test_enabled_keras_models_use_raw_pixel_range():
    enabled_keras = [
        item
        for item in read_model_configs()
        if item.get("enabled") and item.get("framework") == "keras"
    ]
    assert enabled_keras
    assert all(item.get("input_range") == "0_255" for item in enabled_keras)


def test_verified_benchmark_ranking_uses_full_mnist_results():
    by_key = {item["key"]: item for item in read_model_configs()}
    assert by_key["cnn"]["test_accuracy"] == pytest.approx(0.9912)
    assert by_key["neural_network"]["test_accuracy"] == pytest.approx(0.9802)
    assert by_key["cnn"]["test_accuracy"] > by_key["neural_network"]["test_accuracy"]

    summary_path = config.BASE / "models" / "metadata" / "evaluation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sample_count"] == 10_000
    assert summary["ranking"][0] == "CNN"
    assert not summary["failed_models"]


def test_current_pipeline_version_is_explicit():
    assert config.PIPELINE_VERSION == "2.0.0"


def test_probability_normalisation():
    result = normalise_probabilities(np.arange(10, dtype=float), 10)
    assert result.shape == (10,)
    assert np.isclose(result.sum(), 1.0)

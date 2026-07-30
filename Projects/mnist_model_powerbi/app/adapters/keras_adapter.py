from __future__ import annotations

import time

import numpy as np
import tensorflow as tf

from .base import BaseAdapter
from .keras_custom_objects import CUSTOM_OBJECTS
from ..preprocessing.generic import load_image


class KerasAdapter(BaseAdapter):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.model = tf.keras.models.load_model(
            self.path,
            compile=False,
            custom_objects=CUSTOM_OBJECTS,
            safe_mode=False,
        )

    def _adapt_input(self, array: np.ndarray) -> np.ndarray:
        expected = self.model.input_shape
        if isinstance(expected, list):
            if len(expected) != 1:
                raise ValueError("Only single-input classifiers are supported")
            expected = expected[0]
        expected = tuple(expected)
        actual = tuple(array.shape)
        if len(expected) == 2 and len(actual) == 4:
            flattened = int(np.prod(actual[1:]))
            if expected[-1] is None or int(expected[-1]) == flattened:
                return array.reshape(actual[0], flattened)
        if len(expected) != len(actual):
            raise ValueError(f"Input rank mismatch: model expects {expected}, received {actual}")
        for wanted, received in zip(expected[1:], actual[1:]):
            if wanted is not None and int(wanted) != int(received):
                raise ValueError(f"Input shape mismatch: model expects {expected}, received {actual}")
        return array

    def predict(self, image_path: str) -> dict:
        array = self._adapt_input(load_image(image_path, self.cfg))
        started = time.perf_counter()
        prediction = np.asarray(self.model.predict(array, verbose=0))
        inference_ms = (time.perf_counter() - started) * 1000.0
        if prediction.ndim == 2 and prediction.shape[0] == 1:
            raw = prediction[0]
        elif prediction.ndim == 1:
            raw = prediction
        else:
            raise ValueError(f"Expected one classification vector, received {prediction.shape}")
        return {"probabilities": raw.astype(float), "inference_ms": inference_ms}

from __future__ import annotations

import time

import numpy as np

from .base import BaseAdapter
from ..preprocessing.generic import load_image


class OnnxAdapter(BaseAdapter):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        import onnxruntime as ort
        self.session = ort.InferenceSession(str(self.path), providers=["CPUExecutionProvider"])
        self.input_meta = self.session.get_inputs()[0]
        self.output_meta = self.session.get_outputs()[0]
        self.input_name = str(cfg.get("input_name") or self.input_meta.name)
        self.output_name = str(cfg.get("output_name") or self.output_meta.name)

    def predict(self, image_path: str) -> dict:
        array = np.asarray(load_image(image_path, self.cfg), dtype=np.float32)
        if array.ndim != 4:
            raise ValueError(f"Expected a four-dimensional image tensor, received {array.shape}")
        channels = int(self.cfg.get("channels", 1))
        # Colab export uses NCHW: [batch, channel, height, width].
        if array.shape[-1] == channels:
            array = np.transpose(array, (0, 3, 1, 2))
        elif array.shape[1] != channels:
            raise ValueError(f"Channel mismatch: expected {channels}, received {array.shape}")
        array = np.ascontiguousarray(array, dtype=np.float32)
        started = time.perf_counter()
        raw = np.asarray(self.session.run([self.output_name], {self.input_name: array})[0])[0]
        inference_ms = (time.perf_counter() - started) * 1000.0
        return {"probabilities": raw.astype(float), "inference_ms": inference_ms}

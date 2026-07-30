from __future__ import annotations

import time

import numpy as np

from .base import BaseAdapter
from ..preprocessing.generic import load_image


class PyTorchAdapter(BaseAdapter):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        import torch
        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self.model = torch.jit.load(str(self.path), map_location=self.device)
        except Exception as exc:
            raise RuntimeError("Expected a valid TorchScript .pt model") from exc
        self.model.eval()

    def predict(self, image_path: str) -> dict:
        array = np.asarray(load_image(image_path, self.cfg), dtype=np.float32)
        if array.ndim != 4:
            raise ValueError(f"Expected a four-dimensional image tensor, received {array.shape}")
        channels = int(self.cfg.get("channels", 1))
        if array.shape[-1] == channels:
            array = np.transpose(array, (0, 3, 1, 2))
        elif array.shape[1] != channels:
            raise ValueError(f"Channel mismatch: expected {channels}, received {array.shape}")
        tensor = self.torch.from_numpy(np.ascontiguousarray(array)).to(self.device)
        started = time.perf_counter()
        with self.torch.no_grad():
            output = self.model(tensor)
        if self.device.type == "cuda":
            self.torch.cuda.synchronize()
        inference_ms = (time.perf_counter() - started) * 1000.0
        if isinstance(output, (tuple, list)):
            output = output[0]
        raw = output.detach().cpu().numpy()[0]
        return {"probabilities": raw.astype(float), "inference_ms": inference_ms}

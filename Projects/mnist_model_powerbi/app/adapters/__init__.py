from __future__ import annotations

from .keras_adapter import KerasAdapter


def build_adapter(cfg: dict):
    framework = str(cfg["framework"]).lower()
    if framework in {"keras", "tensorflow"}:
        return KerasAdapter(cfg)
    if framework == "pytorch":
        from .pytorch_adapter import PyTorchAdapter
        return PyTorchAdapter(cfg)
    if framework == "onnx":
        from .onnx_adapter import OnnxAdapter
        return OnnxAdapter(cfg)
    raise ValueError(f"Unsupported framework: {framework}")

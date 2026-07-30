from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from .. import config


class BaseAdapter(ABC):
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.key = str(cfg["key"])
        self.display_name = str(cfg["display_name"])
        self.version = str(cfg.get("version", "1.0.0"))
        self.path = config.BASE / str(cfg["model_path"])
        class_map_path = config.BASE / str(cfg["class_map"])
        self.class_map: dict[str, str] = json.loads(class_map_path.read_text(encoding="utf-8"))
        if len(self.class_map) != 10:
            raise ValueError(f"MNIST class map must contain exactly 10 classes: {class_map_path}")

    @abstractmethod
    def predict(self, image_path: str) -> dict[str, Any]:
        raise NotImplementedError

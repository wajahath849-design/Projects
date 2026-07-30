from __future__ import annotations
from tensorflow import keras
from .config import NN_MODEL_PATH, get_cnn_model_path

class ModelBundle:
    def __init__(self) -> None:
        if not NN_MODEL_PATH.exists():
            raise FileNotFoundError(f"Missing model: {NN_MODEL_PATH}")
        cnn_path = get_cnn_model_path()
        if not cnn_path.exists():
            raise FileNotFoundError(f"Missing CNN model: {cnn_path}")

        self.neural_network = keras.models.load_model(NN_MODEL_PATH)
        self.cnn = keras.models.load_model(cnn_path)

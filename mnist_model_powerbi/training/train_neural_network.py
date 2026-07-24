from pathlib import Path
import numpy as np
from tensorflow import keras
from tensorflow.keras import layers

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "training"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

x_train = np.load(DATA / "x_train_nn.npy")
y_train = np.load(DATA / "y_train.npy")

model = keras.Sequential([
    layers.Input((784,)),
    layers.Dense(256, activation="relu"),
    layers.Dropout(0.30),
    layers.Dense(128, activation="relu"),
    layers.Dropout(0.20),
    layers.Dense(10, activation="softmax"),
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
model.fit(x_train, y_train, validation_split=0.2, epochs=15, batch_size=128,
          callbacks=[keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)])
model.save(MODELS / "neural_network.keras")
print("Saved neural_network.keras")

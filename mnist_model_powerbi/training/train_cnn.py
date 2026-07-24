from pathlib import Path
import numpy as np
from tensorflow import keras
from tensorflow.keras import layers

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "training"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

x_train = np.load(DATA / "x_train_cnn.npy")
y_train = np.load(DATA / "y_train.npy")

model = keras.Sequential([
    layers.Input((28, 28, 1)),
    layers.Conv2D(32, 3, activation="relu", padding="same"),
    layers.BatchNormalization(),
    layers.MaxPooling2D(),
    layers.Conv2D(64, 3, activation="relu", padding="same"),
    layers.BatchNormalization(),
    layers.MaxPooling2D(),
    layers.Conv2D(128, 3, activation="relu", padding="same"),
    layers.Flatten(),
    layers.Dense(128, activation="relu"),
    layers.Dropout(0.30),
    layers.Dense(10, activation="softmax"),
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
checkpoint = keras.callbacks.ModelCheckpoint(
    MODELS / "cnn_best.keras", monitor="val_accuracy", save_best_only=True, mode="max"
)
model.fit(x_train, y_train, validation_split=0.2, epochs=15, batch_size=128,
          callbacks=[checkpoint, keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)])
model.save(MODELS / "cnn.keras")
print("Saved cnn.keras and cnn_best.keras")

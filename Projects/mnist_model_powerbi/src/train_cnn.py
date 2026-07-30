from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
from tensorflow import keras
from tensorflow.keras import layers


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"
POWERBI_EXPORT_DIR = PROJECT_ROOT / "data" / "powerbi_exports"
RESULTS_DIR = PROJECT_ROOT / "reports" / "model_results"


def train_cnn() -> None:
    """Train a convolutional neural network on MNIST."""

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    POWERBI_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading processed MNIST data...")

    x_train = np.load(PROCESSED_DIR / "x_train_cnn.npy")
    x_test = np.load(PROCESSED_DIR / "x_test_cnn.npy")
    y_train = np.load(PROCESSED_DIR / "y_train.npy")
    y_test = np.load(PROCESSED_DIR / "y_test.npy")

    print(f"Training data shape: {x_train.shape}")
    print(f"Testing data shape: {x_test.shape}")

    model = keras.Sequential(
        [
            layers.Input(shape=(28, 28, 1), name="input_image"),

            layers.Conv2D(
                32,
                kernel_size=(3, 3),
                activation="relu",
                padding="same",
                name="conv_1",
            ),
            layers.BatchNormalization(name="batch_norm_1"),
            layers.MaxPooling2D(
                pool_size=(2, 2),
                name="max_pool_1",
            ),

            layers.Conv2D(
                64,
                kernel_size=(3, 3),
                activation="relu",
                padding="same",
                name="conv_2",
            ),
            layers.BatchNormalization(name="batch_norm_2"),
            layers.MaxPooling2D(
                pool_size=(2, 2),
                name="max_pool_2",
            ),

            layers.Conv2D(
                128,
                kernel_size=(3, 3),
                activation="relu",
                padding="same",
                name="conv_3",
            ),

            layers.Flatten(name="flatten"),

            layers.Dense(
                128,
                activation="relu",
                name="dense_128",
            ),
            layers.Dropout(
                0.30,
                name="dropout",
            ),

            layers.Dense(
                10,
                activation="softmax",
                name="output",
            ),
        ],
        name="mnist_cnn",
    )

    model.compile(
        optimizer=keras.optimizers.Adam(
            learning_rate=0.001
        ),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=3,
            restore_best_weights=True,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=0.00001,
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=MODEL_DIR / "cnn_best.keras",
            monitor="val_accuracy",
            save_best_only=True,
            mode="max",
        ),
    ]

    print("\nTraining CNN model...")

    start_time = time.time()

    history = model.fit(
        x_train,
        y_train,
        validation_split=0.20,
        epochs=15,
        batch_size=128,
        callbacks=callbacks,
        verbose=1,
    )

    training_time_seconds = time.time() - start_time

    print("\nEvaluating CNN model...")

    test_loss, test_accuracy = model.evaluate(
        x_test,
        y_test,
        verbose=0,
    )

    model_path = MODEL_DIR / "cnn.keras"
    model.save(model_path)

    history_df = pd.DataFrame(history.history)
    history_df.insert(
        0,
        "Epoch",
        range(1, len(history_df) + 1),
    )
    history_df.insert(
        0,
        "Model",
        "CNN",
    )

    history_df.rename(
        columns={
            "accuracy": "TrainingAccuracy",
            "loss": "TrainingLoss",
            "val_accuracy": "ValidationAccuracy",
            "val_loss": "ValidationLoss",
            "learning_rate": "LearningRate",
        },
        inplace=True,
    )

    history_df.to_csv(
        POWERBI_EXPORT_DIR / "cnn_training_history.csv",
        index=False,
    )

    model_summary = {
        "Model": "CNN",
        "TestAccuracy": float(test_accuracy),
        "TestLoss": float(test_loss),
        "TrainingTimeSeconds": float(
            training_time_seconds
        ),
        "EpochsCompleted": len(
            history.history["loss"]
        ),
        "ParameterCount": int(
            model.count_params()
        ),
        "ModelFile": model_path.name,
    }

    pd.DataFrame([model_summary]).to_csv(
        POWERBI_EXPORT_DIR / "cnn_summary.csv",
        index=False,
    )

    with open(
        RESULTS_DIR / "cnn_summary.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            model_summary,
            file,
            indent=4,
        )

    print("\nCNN training completed successfully.")
    print(f"Test accuracy: {test_accuracy:.4f}")
    print(f"Test loss: {test_loss:.4f}")
    print(
        f"Training time: "
        f"{training_time_seconds:.2f} seconds"
    )
    print(
        f"Parameters: "
        f"{model.count_params():,}"
    )
    print(f"Model saved to: {model_path}")


if __name__ == "__main__":
    train_cnn()
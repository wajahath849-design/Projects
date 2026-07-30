from pathlib import Path

import numpy as np
import pandas as pd
from tensorflow.keras.datasets import mnist


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
POWERBI_EXPORT_DIR = PROJECT_ROOT / "data" / "powerbi_exports"


def prepare_mnist_data() -> None:
    """Download, normalize, reshape, and save the MNIST dataset."""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    POWERBI_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading and loading MNIST dataset...")

    (x_train, y_train), (x_test, y_test) = mnist.load_data()

    print(f"Original training shape: {x_train.shape}")
    print(f"Original testing shape: {x_test.shape}")

    # Normalize pixel values from 0–255 to 0–1
    x_train_normalized = x_train.astype("float32") / 255.0
    x_test_normalized = x_test.astype("float32") / 255.0

    # CNN input format: samples, height, width, channels
    x_train_cnn = np.expand_dims(x_train_normalized, axis=-1)
    x_test_cnn = np.expand_dims(x_test_normalized, axis=-1)

    # Neural-network input format: samples, 784 pixels
    x_train_nn = x_train_normalized.reshape(x_train_normalized.shape[0], -1)
    x_test_nn = x_test_normalized.reshape(x_test_normalized.shape[0], -1)

    # Save processed NumPy arrays
    np.save(PROCESSED_DIR / "x_train_nn.npy", x_train_nn)
    np.save(PROCESSED_DIR / "x_test_nn.npy", x_test_nn)

    np.save(PROCESSED_DIR / "x_train_cnn.npy", x_train_cnn)
    np.save(PROCESSED_DIR / "x_test_cnn.npy", x_test_cnn)

    np.save(PROCESSED_DIR / "y_train.npy", y_train)
    np.save(PROCESSED_DIR / "y_test.npy", y_test)

    # Export dataset summary for Power BI
    dataset_summary = pd.DataFrame(
        [
            {
                "Dataset": "Training",
                "NumberOfImages": len(x_train),
                "ImageHeight": x_train.shape[1],
                "ImageWidth": x_train.shape[2],
                "NumberOfClasses": len(np.unique(y_train)),
            },
            {
                "Dataset": "Testing",
                "NumberOfImages": len(x_test),
                "ImageHeight": x_test.shape[1],
                "ImageWidth": x_test.shape[2],
                "NumberOfClasses": len(np.unique(y_test)),
            },
        ]
    )

    dataset_summary.to_csv(
        POWERBI_EXPORT_DIR / "dataset_summary.csv",
        index=False,
    )

    # Export digit distribution for Power BI
    train_distribution = (
        pd.Series(y_train)
        .value_counts()
        .sort_index()
        .rename_axis("Digit")
        .reset_index(name="ImageCount")
    )
    train_distribution["Dataset"] = "Training"

    test_distribution = (
        pd.Series(y_test)
        .value_counts()
        .sort_index()
        .rename_axis("Digit")
        .reset_index(name="ImageCount")
    )
    test_distribution["Dataset"] = "Testing"

    digit_distribution = pd.concat(
        [train_distribution, test_distribution],
        ignore_index=True,
    )

    digit_distribution = digit_distribution[
        ["Dataset", "Digit", "ImageCount"]
    ]

    digit_distribution.to_csv(
        POWERBI_EXPORT_DIR / "digit_distribution.csv",
        index=False,
    )

    print("\nDataset preparation completed successfully.")
    print(f"Neural-network training shape: {x_train_nn.shape}")
    print(f"CNN training shape: {x_train_cnn.shape}")
    print(f"Training labels shape: {y_train.shape}")
    print(f"Testing labels shape: {y_test.shape}")
    print(f"Files saved in: {PROCESSED_DIR}")
    print(f"Power BI exports saved in: {POWERBI_EXPORT_DIR}")


if __name__ == "__main__":
    prepare_mnist_data()
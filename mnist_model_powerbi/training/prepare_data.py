from pathlib import Path
import numpy as np
from tensorflow.keras.datasets import mnist

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "training"
OUT.mkdir(parents=True, exist_ok=True)

(x_train, y_train), (x_test, y_test) = mnist.load_data()
x_train = x_train.astype("float32") / 255.0
x_test = x_test.astype("float32") / 255.0

np.save(OUT / "x_train_nn.npy", x_train.reshape(-1, 784))
np.save(OUT / "x_test_nn.npy", x_test.reshape(-1, 784))
np.save(OUT / "x_train_cnn.npy", x_train[..., None])
np.save(OUT / "x_test_cnn.npy", x_test[..., None])
np.save(OUT / "y_train.npy", y_train)
np.save(OUT / "y_test.npy", y_test)
print("MNIST data prepared.")

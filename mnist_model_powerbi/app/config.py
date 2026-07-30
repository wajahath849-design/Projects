from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
DATA_DIR = PROJECT_ROOT / "data"
INCOMING_DIR = DATA_DIR / "incoming"
PROCESSED_DIR = DATA_DIR / "processed"
ARCHIVE_DIR = DATA_DIR / "archive"
FAILED_DIR = DATA_DIR / "failed"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / "application.log"

NN_MODEL_PATH = MODELS_DIR / "neural_network.keras"
CNN_BEST_MODEL_PATH = MODELS_DIR / "cnn_best.keras"
CNN_MODEL_PATH = MODELS_DIR / "cnn.keras"

SQL_SERVER = os.getenv("MNIST_SQL_SERVER", r"localhost\SQLEXPRESS")
SQL_DATABASE = os.getenv("MNIST_SQL_DATABASE", "MNISTAnalytics")
SQL_DRIVER = os.getenv("MNIST_SQL_DRIVER", "ODBC Driver 17 for SQL Server")

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
PROCESS_EXISTING_ON_START = True
SKIP_DUPLICATE_NAMES = True

def ensure_directories() -> None:
    for path in [
        INCOMING_DIR, PROCESSED_DIR, ARCHIVE_DIR,
        FAILED_DIR, MODELS_DIR, LOGS_DIR
    ]:
        path.mkdir(parents=True, exist_ok=True)

def get_cnn_model_path() -> Path:
    return CNN_BEST_MODEL_PATH if CNN_BEST_MODEL_PATH.exists() else CNN_MODEL_PATH

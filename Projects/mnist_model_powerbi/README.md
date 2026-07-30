# AI Image Classification and Model Comparison Platform

A Windows-based MNIST inference platform with six model architectures, SQL Server
reporting views, a FastAPI image endpoint, and a four-page Power BI dashboard.

## Included

- File-watcher inference pipeline with single-instance protection
- Neural Network, CNN, MobileNetV2, ResNet50, EfficientNetB0, and Vision Transformer support
- SQL Server Express schema and reporting views
- Local FastAPI service for original and processed images
- Power BI pages for Executive Overview, Live Prediction, Model Performance, and Data Explorer

Trained model binaries are intentionally excluded from Git because they total more
than 280 MB and one file exceeds GitHub's normal 100 MB limit. Model metadata and
installation instructions are included.

## Requirements

- Windows 10 or 11
- Python 3.12
- SQL Server Express with the `SQLEXPRESS` instance
- Microsoft ODBC Driver 18 for SQL Server
- Power BI Desktop

Clone the repository to a short path such as `C:\AIModelAnalytics`. This keeps every
Power BI project file comfortably below the Windows path-length limit.

## Installation

1. Run `INSTALL_PROJECT.ps1`.
2. Add the trained files described in `models\PLACE_TRAINED_MODELS_HERE.md`.
3. Run `REGISTER_MODELS.bat`.
4. If Power BI cannot connect to `localhost,14330`, run
   `powerbi\enable_sqlexpress_tcp.ps1` as Administrator and restart SQL Server Express.
5. Run `VERIFY_PROJECT.bat`.

The default application connection is `localhost\SQLEXPRESS`, and the database name
is `AIModelAnalytics`. Override local settings by copying `.env.example` to `.env`.

## Running the project

1. Start the API and watcher with `START_PROJECT.bat`.
2. Copy a digit image into `data\incoming`.
3. Open `powerbi\PBI\AI Model Analytics.pbip`.
4. Stop the services with `STOP_PROJECT.bat` when finished.

The actual label is read from filenames such as `digit_3.png`. Unlabelled images
still receive predictions but are excluded from observed accuracy until a label is
provided.

## Accuracy shown in Power BI

The verified comparison uses the canonical 10,000-image MNIST test split:

- CNN: 99.12%
- Vision Transformer: 98.75%
- Neural Network: 98.02%
- ResNet50: 97.61%
- EfficientNetB0: 96.18%
- MobileNetV2: 91.48%

Live accuracy is a separate metric based only on labelled images processed by the
current pipeline.

## Repository hygiene

The repository excludes virtual environments, local `.env` values, logs, runtime
images, Power BI caches, database files, ZIP/PBIX exports, and trained model
binaries. See `docs\VALIDATION.md` for the latest verified test summary.

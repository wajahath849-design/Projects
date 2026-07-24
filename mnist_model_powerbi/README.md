# MNIST AI + Power BI Analytics Platform

An end-to-end portfolio project combining:

- Dense Neural Network
- Convolutional Neural Network
- Automatic custom-image preprocessing to 28×28
- Folder-based automatic prediction
- SQL Server storage
- Power BI DirectQuery
- Automatic page refresh

## 1. Prerequisites

Install:

- Python 3.11 or 3.12
- SQL Server Express
- SQL Server Management Studio
- Microsoft ODBC Driver 18 for SQL Server
- Power BI Desktop

## 2. Create environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No PowerShell activation is required.

## 3. Create database

Open `database/setup_database.sql` in SSMS and execute it.

Default SQL instance:

```text
localhost\SQLEXPRESS
```

Change `app/config.py` or set environment variables when needed.

## 4. Models

Copy your existing files into `models/`:

```text
neural_network.keras
cnn.keras
cnn_best.keras
```

Or train them:

```powershell
.\.venv\Scripts\python.exe training\prepare_data.py
.\.venv\Scripts\python.exe training\train_neural_network.py
.\.venv\Scripts\python.exe training\train_cnn.py
```

## 5. Test database

```powershell
.\.venv\Scripts\python.exe test_database.py
```

## 6. Start automatic prediction

```powershell
.\.venv\Scripts\python.exe start_project.py
```

Drop images into:

```text
data\incoming
```

The system:

1. Detects the file.
2. Converts it to MNIST style.
3. Resizes and centres it to 28×28.
4. Runs both models.
5. Inserts results into SQL Server.
6. Moves the original image to `data\archive`.

A filename containing exactly one digit, such as `digit_7.png`, is automatically labelled as digit 7.

## 7. Power BI

In Power BI Desktop:

1. Get Data → SQL Server.
2. Server: `localhost\SQLEXPRESS`
3. Database: `MNISTAnalytics`
4. Data connectivity mode: **DirectQuery**
5. Load:
   - `dbo.CustomImagePredictions`
   - `dbo.vw_LatestPredictions`
   - `dbo.vw_PredictionSummary`
   - `dbo.vw_ConfusionMatrix`

For the live prediction page:

1. Click an empty area of the page.
2. Format page → Page refresh.
3. Turn it on.
4. Select Fixed interval.
5. Use an interval supported by your Power BI environment.

## Important limitation

Power BI Desktop must remain open for automatic page refresh. For Power BI Service with a local SQL Server source, install and configure an on-premises data gateway.

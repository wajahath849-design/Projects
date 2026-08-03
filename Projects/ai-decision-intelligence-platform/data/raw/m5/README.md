# M5 dataset placement

Download the M5 Forecasting - Accuracy competition data manually from Kaggle
after accepting Kaggle's applicable terms. Do not commit or redistribute the
source files through this repository.

Copy these three original files into this directory:

- `calendar.csv`
- `sales_train_validation.csv`
- `sell_prices.csv`

The resulting layout must be:

```text
data/raw/m5/calendar.csv
data/raw/m5/sales_train_validation.csv
data/raw/m5/sell_prices.csv
```

Before loading, inspect the files without changing them:

```powershell
Get-ChildItem data\raw\m5\*.csv | Select-Object Name, Length
Get-FileHash data\raw\m5\*.csv -Algorithm SHA256
```

Then run the full-file loader. It validates file presence, required columns,
ordered daily demand columns, identifiers, dates, duplicates, nonnegative demand
and prices, and calendar-week references before committing each bounded chunk:

```powershell
.\.venv\Scripts\python.exe scripts\load_m5_data.py
```

The M5 historical files are real competition data. Operational supplier,
warehouse, transportation, inventory, and purchase-order data introduced in
later phases will be synthetic and must not be interpreted as Walmart operations.

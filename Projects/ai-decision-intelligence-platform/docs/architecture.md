# Architecture

```mermaid
flowchart LR
    M5["M5 CSV files"] --> V["Schema and quality validation"]
    SYN["Synthetic enterprise generator"] --> SQL["SQL Server analytical model"]
    V --> SQL
    SQL --> FE["Leakage-safe feature pipeline"]
    FE --> MODELS["Seasonal Naive / XGBoost / LightGBM"]
    MODELS --> SELECT["Measured model selection"]
    SELECT --> FC["7 / 30 / 90-day forecasts"]
    SELECT --> SHAP["Local SHAP explanations"]
    FC --> INV["Inventory risk intelligence"]
    INV --> OPT["OR-Tools replenishment optimization"]
    OPT --> SCN["Scenario simulation"]
    FC --> API["FastAPI"]
    SHAP --> API
    INV --> API
    OPT --> API
    SCN --> API
    SQL --> PBI["Power BI SQL views and DAX package"]
    FC --> SQL
    SHAP --> SQL
    INV --> SQL
    OPT --> SQL
    SCN --> SQL
    CI["GitHub Actions / sample verification"] --> V
    CI --> FE
    CI --> MODELS
    CI --> OPT
    CI --> API
    CI --> PBI
```

The platform is production-style and portfolio-grade, not production-ready. SQL Server
Express with Windows authentication is the primary local workflow. Container SQL Server
and SQL authentication are optional for CI and portable demonstrations.

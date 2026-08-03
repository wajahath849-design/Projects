# API documentation

Start locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn decision_intelligence.api.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger UI, `/redoc` for ReDoc, and
`/openapi.json` for the machine-readable contract.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API health |
| GET | `/health/database` | SQL connectivity |
| GET | `/health/models` | production-model state |
| GET | `/api/v1/forecasts` | paged forecast detail |
| GET | `/api/v1/forecasts/{product_id}` | product forecasts |
| POST | `/api/v1/forecasts/run` | idempotent forecast upsert |
| GET | `/api/v1/forecast-metrics` | model comparison metrics |
| GET | `/api/v1/inventory/status` | all inventory classifications |
| GET | `/api/v1/inventory/risks` | Critical and At Risk inventory |
| GET | `/api/v1/inventory/{product_id}` | product inventory detail |
| GET | `/api/v1/recommendations` | validated recommendations |
| GET | `/api/v1/recommendations/{product_id}` | product recommendations |
| POST | `/api/v1/recommendations/run` | rerun optimization |
| GET | `/api/v1/scenarios` | scenario definitions |
| POST | `/api/v1/scenarios` | validate and create a scenario |
| POST | `/api/v1/scenarios/{scenario_id}/run` | execute a scenario |
| GET | `/api/v1/scenarios/{scenario_id}/results` | baseline comparison |
| GET | `/api/v1/explanations/{forecast_id}` | ranked local explanations |

Invalid payloads return 422, missing resources 404, duplicate scenario IDs 409, and health
dependency failures 503. The portfolio sample has no authentication or rate limiting; add
an identity provider, authorization, audit policy, and throttling before any deployment.

# Metric Mirage

**A dashboard that audits other dashboards.**

Metric Mirage reviews the evidence behind business KPI claims. Give it a CSV, a ratio metric and a statement such as “the new checkout increased conversion”; it compares two periods and checks segment reversals, population composition, input quality and sampling reliability. The statement provides context; the engine does not interpret its causal meaning or verify arbitrary natural-language claims.

The included demo reveals a Simpson's-paradox trap: total conversion rises while both desktop and mobile conversion fall.

## Why this project exists

Most analytics portfolios visualize a result. Metric Mirage asks whether the result should influence a decision. It demonstrates full-stack product engineering, statistical reasoning, data-quality practice and clear executive communication in one application.

## Product highlights

- Claim, metric definition and evidence in one review workflow.
- Automatic segment-reversal and Simpson's-paradox detection.
- Descriptive comparison using a fixed population mix.
- Composition-drift, input-integrity, outlier and reliability checks.
- Evidence score with visible severity penalties and check coverage; a review heuristic, not a probability or statistical confidence level.
- Evidence-linked findings and recommended next actions.
- Interactive trend comparison, segment tables and inspectable metric definitions.
- Searchable review history for the current browser session.
- Decision report with browser print/save-as-PDF and downloadable JSON evidence.
- Anonymous one-shot CSV analysis plus separate authenticated persistent API resources.
- Deterministic calculations: no LLM generates or changes statistical results.
- Responsive, accessible interface with loading, error and offline-demo states.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, custom SVG visualization |
| Backend | Django, Django REST Framework |
| Analytics | Pandas, NumPy, deterministic statistical checks |
| Storage | PostgreSQL in Docker; SQLite for local setup |
| Delivery | Docker Compose, Nginx, Gunicorn, GitHub Actions |
| Quality | Pytest, Django system checks, Vitest, TypeScript build |

## Fastest start: Docker

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). The frontend proxies API requests to Django. PostgreSQL stores records created through the authenticated API; reviews created in the current frontend remain in browser memory and are cleared on refresh.

## Local development on Windows

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
Set-Location backend
python manage.py migrate
python manage.py runserver
```

Frontend in a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Try your own dataset

Use **New review** and upload a CSV. A ready-to-use example is provided at [`data/checkout_demo.csv`](data/checkout_demo.csv), also downloadable from **Data & definitions**.

Required configuration:

- A date column.
- A non-negative numerator such as `conversions`.
- A positive denominator such as `sessions`.
- Optional segment columns such as `device`; only the first is analyzed. At least two groups present in both periods are needed for composition checks.
- An optional split date; the middle unique valid date is used when omitted (the later middle date for an even count).

At least four valid dated observations are required, with observations in both comparison periods. Invalid split dates or unreadable CSV files return a validation message. Unsupported checks are shown as **Not assessed**, never counted as passed.

The public upload endpoint accepts CSV files up to 10 MB and is throttled. It analyzes uploads without creating persistent dataset or audit records. Persistent datasets, metric definitions and audit records are available through separate authenticated API endpoints; the frontend has no sign-in or saved-account workflow yet.

## Reviewing and keeping a result

1. Inspect the reported change alongside the fixed-mix comparison on **Review overview**.
2. Open **Checks** for each result and its assumptions, or **Data definition** for the exact columns, observed date ranges and row counts.
3. Use **All reviews** to search and reopen results created in the current session.
4. Open **Decision report** to print or save a PDF through the browser. **Download evidence** exports the complete JSON result, including findings, check statuses, metric contract, limitations and methodology.

Download evidence before refreshing if you need to retain an uploaded review. There is no JSON import or persistent frontend history in this version.

If the API is unavailable, the interface shows a bundled, clearly labeled sample report. That fallback lets you explore the review screens; it does not perform CSV analysis in the browser. Start Django to analyze your own data.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health/` | Service health |
| `GET` | `/api/demo/` | Reproducible demo audit |
| `POST` | `/api/analyze/` | One-shot CSV audit |
| `POST` | `/api/auth/login/` | Obtain an API token |
| CRUD | `/api/datasets/` | Persistent datasets |
| CRUD | `/api/metrics/` | Metric contracts |
| `GET/POST` | `/api/audits/` | Stored decision audits |

## Verification

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe manage.py check

Set-Location ..\frontend
npm test
npm run build
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Audit methodology](docs/METHODOLOGY.md)
- [Demo data dictionary](docs/DATA_DICTIONARY.md)
- [Portfolio case study](docs/CASE_STUDY.md)

## Two-minute interview explanation

> Metric Mirage addresses a problem I noticed in analytics products: they make it easy to visualize KPI movement but do not test whether the implied conclusion is reliable. I built a Django and React application where an analyst submits a business claim and metric contract. A deterministic Pandas engine checks data integrity, segment reversals, composition drift, sampling reliability and outlier sensitivity. In the demo, aggregate checkout conversion increases, but both device segments decline. Reweighting the new period using the old traffic mix reverses the result, so the product recommends against attributing the improvement to the release. I separated the analytics engine from the API so the methodology is independently testable, exposed every finding as structured evidence, and packaged the product with PostgreSQL, Docker, CI and a printable decision report.

## CV bullets

- Built a full-stack analytics-integrity platform with Django, React, TypeScript and PostgreSQL that audits business KPI claims rather than only visualizing them.
- Designed deterministic statistical checks for Simpson's paradox, population-mix drift, outlier sensitivity, input-quality failures and proportion reliability.
- Implemented a decision report with JSON export and browser PDF printing, CSV analysis, authenticated REST resources, automated tests, Docker configuration and CI.

## Limitations

Metric Mirage detects risks in observational comparisons; it does not prove causality, adjust for seasonality or establish that a product change caused the observed movement. Results depend on an appropriate metric definition and meaningful segment selection. Only the first segment column is analyzed, using groups present in both periods. Reliability testing requires suitable integer success/trial counts and assumes independent observations.

The evidence score starts at 100 and subtracts fixed penalties for findings. Related findings can overlap; skipped checks do not lower the score. A high score with limited coverage is therefore not proof of a reliable conclusion. See [Audit methodology](docs/METHODOLOGY.md) for exact rules.

This is a runnable portfolio application for ratio metrics and CSVs up to 10 MB. Public production use needs deployment-specific configuration, resource controls and authorization review. Authentication on the persistent API does not provide per-user or per-organization data isolation in this version.

Licensed under the [MIT License](LICENSE).

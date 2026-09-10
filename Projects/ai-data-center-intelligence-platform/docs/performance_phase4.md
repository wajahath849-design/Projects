# Phase 4 Hybrid Fast Router

## Result

The application now classifies common questions before RAG or Ollama. Definitions, annual KPIs, comparisons, trends, rankings, forecasts, and router-only safety/clarification outcomes use deterministic paths. Ad-hoc grains and complex investigative questions retain the validated Text-to-SQL path.

In the 30-question benchmark, **13 questions (43.3%)** used new fast analytics/definition paths, ten used the existing forecast path, five stopped in the router, and only two required the ad-hoc AI path. The full suite passed **99 tests**.

## Measured behavior

| Execution path | Questions | P50 |
|---|---:|---:|
| Fast definition | 2 | 3.808 ms |
| Fast KPI | 3 | 6.273 ms |
| Fast ranking | 1 | 4.775 ms |
| Fast comparison | 3 | 22.166 ms |
| Fast trend | 4 | 22.846 ms |
| Forecast | 10 | 28.444 ms |
| AI Text-to-SQL candidates | 2 | Offline generator only |

Overall offline P50 was 21.693 ms and P95 was 53.883 ms. The first chart construction produced the expected cold Plotly cost and dominated the 254.576 ms maximum.

A live-pipeline smoke test with Ollama available confirmed zero model calls:

| Question | Path | LLM calls | Total |
|---|---|---:|---:|
| What is PUE? | Fast definition | 0 | 10.133 ms |
| Highest PUE in 2020 | Fast ranking | 0 | 55.594 ms |
| Dublin vs Frankfurt PUE, 2023 | Fast comparison | 0 | 7.682 ms |
| Annual cooling cost, 2015–2025 | Fast trend | 0 | 5.153 ms |

The ranking smoke includes the first SQL validator/import cost. Subsequent fast questions were 5–10 ms before browser rendering.

## Design

- `FastQueryRouter` uses deterministic intent, metric, facility, year, and grain recognition.
- `QueryTemplateEngine` uses allow-listed metric-to-column mappings over `agg_facility_yearly`.
- User filters are passed as SQLite parameters rather than concatenated into SQL.
- Every template still passes the independent SQL validator and read-only executor.
- Weighted rollups use measurement counts; sums remain sums.
- Unsupported detail grains—server, server type, rack, day, month, quarter, severity, and root cause—remain on the AI path.
- Definitions are read directly from the governed business glossary.

## Correctness boundary fixes

Testing caught and corrected two routing risks:

1. `from 2015 to 2025` initially selected only the endpoint years; the router now expands explicit trend ranges inclusively.
2. A conversational increase/decrease follow-up initially entered a KPI route; direction questions now remain on the existing forecast-direction path.

Facility/year grouping is explicit so `Average CPU utilization by facility by year` returns all 66 governed facility/year rows rather than one fleet scalar.

## Security

Fast paths do not bypass guardrails. Metric expressions and aggregate columns come from code allow-lists, facility/year values use bound parameters, SQL remains read-only, and the existing validator, row limit, and timeout execute before database access.

## Files

Added:

- `src/query_router.py`
- `src/query_templates.py`
- `tests/test_fast_router.py`
- `evaluation/results/performance_phase4_after.json`
- `evaluation/results/phase4_live_smoke.json`
- `evaluation/results/phase4_pytest.xml`

Changed:

- `src/pipeline.py`
- `src/executor.py`
- `tests/test_performance.py`

## Commands

```powershell
python scripts\benchmark_pipeline.py --offline --label phase_4_hybrid_router --output evaluation\results\performance_phase4_after.json
python -m pytest -q -p no:cacheprovider --basetemp="$env:TEMP\ai-dc-phase4-tests" --junitxml=evaluation\results\phase4_pytest.xml
```

## Interview explanation

The hybrid design does not claim that deterministic routes replace AI. It uses deterministic logic where the intent and grain are known, then reserves RAG and Text-to-SQL for genuinely ad-hoc questions. This improves latency and reproducibility while keeping one independent SQL-security boundary for both routes.

Phase 4 is complete.

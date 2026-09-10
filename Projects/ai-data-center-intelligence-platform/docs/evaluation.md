# Evaluation

The evaluation design separates deterministic correctness, security, protected diagnostic cases, performance, and local-model quality.

## Current accepted evidence — 28 August 2026

- Complete regression suite: see `evaluation/results/phase34_pytest.xml`; zero failures and errors are required.
- Offline verified examples: 3/3 executed against SQLite.
- SQL security decisions: 10/10 matched expected allow/block behavior.
- Independent KPI reconciliation: 18/18 metrics passed.
- Forecast coverage: 16/16 supported time-varying metrics have generated validation evidence.
- Protected synthetic root-cause cases: 6/6 passed across incident detection, component identification, evidence retrieval, similar-case retrieval, root-cause category, and recommendation relevance.
- Performance: 30-question offline regression plus separate log-index and routed-RAG benchmarks.
- Power BI source: 17 tables, 30 relationships, 56 DAX measures, 7 populated pages, and 223 native visuals are statically checked.

The combined machine-readable release result is `evaluation/results/advanced_release_validation.json`.

## Run the evaluation

```powershell
python -m evaluation.evaluate
python scripts\validate_kpis.py
python scripts\evaluate_forecasts.py
python evaluation\evaluate_root_cause.py
python -m pytest -q --junitxml evaluation\results\phase34_pytest.xml
python scripts\validate_advanced_release.py
```

`questions.json` contains 48 questions across eight tiers. `forecast_questions.json` adds 16 future-year cases. `ground_truth.json` contains reviewed reference SQL for the three offline examples; results are compared at the database-output level rather than by SQL string. `security_tests.json` covers writes, multiple statements, PRAGMA/ATTACH, unknown schema, and a safe SELECT.

Protected root-cause truth is loaded only by the evaluation runner after production engines are constructed. It is never placed into prompts, retrieval, or production knowledge. The six scenarios are synthetic and deterministic; perfect performance on them is not evidence of real-world causal accuracy.

The offline benchmark measures deterministic application paths, not full Ollama accuracy. Full local-model evaluation should compare normalized result frames and record execution accuracy, result accuracy, answer faithfulness, retrieval relevance, guardrail accuracy, ambiguity handling, paraphrase equivalence, latency, and token use on the user's installed model and hardware.

Power BI Desktop refresh, visual bindings, cross-filter behavior, accessibility, pixel review, and `.pbix` export require an external desktop validation pass.

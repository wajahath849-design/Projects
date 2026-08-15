# Evaluation

`questions.json` contains 48 questions across eight tiers. `forecast_questions.json` adds 16 future-year cases covering supported operational metrics and unsupported static/price requests. `ground_truth.json` contains reviewed reference SQL for the three offline examples; evaluation compares database outputs, not SQL strings. `security_tests.json` covers writes, multi-statements, PRAGMA/ATTACH, unknown schema, and a safe SELECT.

Run:

```powershell
python -m evaluation.evaluate
python -m pytest -q
```

Measured on 14 Aug 2026: the offline baseline passed 10/10 security expectations and executed 3/3 verified SQL examples. This is not a measurement of general Ollama SQL accuracy, answer faithfulness, paraphrase robustness, or latency. Those require the configured local model and repeated full-corpus runs. Raw runtime output is written to `evaluation/results/` and intentionally ignored by Git.

For full evaluation, compare executed result frames with reference result frames using normalized types, ordering rules, numeric tolerances, and set comparison where ordering is irrelevant. Record SQL execution accuracy, result accuracy, answer faithfulness, retrieval relevance, guardrail accuracy, ambiguity accuracy, paraphrase equivalence, latency, tokens, and actual pricing applicable at run time.

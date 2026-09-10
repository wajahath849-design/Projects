# Phase 3 Ollama Performance Optimization

## Technical summary

Phase 3 reduced avoidable local-model work while preserving SQL validation and grounded answers. The ordinary KPI smoke question now makes **one Ollama call instead of two** and completed in **15.227 seconds**, compared with **69.257 seconds** for the same question in the Phase 1 live baseline. That is a measured 78.0% end-to-end reduction on this run.

The SQL prompt was shortened, structured output and temperature zero were retained, output length is bounded, and the model is explicitly held in memory for 30 minutes. Blind RAG top-k reduction was rejected after it produced an invalid table name. The accepted implementation uses four semantic results plus deterministic domain-specific schema inclusion.

All three post-optimization SQL samples passed the independent validator and executed successfully. The full regression suite passed: **92 tests, zero failures, zero errors**.

## Measured baseline and result

The direct benchmark unloaded the model before the first request, then ran two warm requests. It used the same three SQL questions before and after.

| Metric | Before | After | Result |
|---|---:|---:|---:|
| Cold request wall time | 47,698.929 ms | 40,240.148 ms | 15.6% lower |
| Warm request P50 | 40,977.708 ms | 43,744.242 ms | 6.8% higher/noisy |
| Mean prompt tokens | 624.3 | 542.3 | 13.1% lower |
| Mean prompt characters | 2,649.0 | 2,497.7 | 5.7% lower |

The warm three-question result does not establish a per-call inference improvement; CPU inference remained variable and one accepted query required more exact schema context. The reliable application-level improvement is removal of the second model call for ordinary result wording.

For `Which facility had the highest average PUE in 2020?`:

| Measurement | Phase 1 | Phase 3 live smoke |
|---|---:|---:|
| LLM calls | 2 | 1 |
| Total time | 69,256.858 ms | 15,226.951 ms |
| Answer generation | 9,650.441 ms | 1.693 ms |
| Result | Rendering precision fallback | Singapore South, PUE 1.61 |

The comparison is a same-machine engineering measurement, not a production SLA. Local CPU load and model state can materially affect individual runs.

## Implementation

- `OLLAMA_KEEP_ALIVE=30m` keeps the model resident between normal user questions.
- The same Ollama client is reused for SQL and any genuinely necessary narrative answer.
- SQL generation uses a concise prompt, JSON schema output, temperature zero, bounded context, and bounded output tokens.
- Ordinary scalar, entity/value, ranking, and table results use the deterministic grounded renderer.
- Narrative Ollama generation is reserved for questions requesting investigation, correlation, explanation, or interpretation.
- SQL context starts with four semantic results and adds required schema chunks using deterministic domain hints.
- Retrieved questions and knowledge remain explicitly labeled untrusted data.

## Rejected optimization

Reducing top-k without schema guarantees caused `Count incidents by facility and root cause` to generate a query against a nonexistent `incidents` table. That trial was not accepted. The final retrieval path explicitly includes `schema:uptime_incidents` and `schema:facilities`; its generated SQL correctly used `uptime_incidents`.

## Correctness and security

The accepted post-optimization SQL samples returned 1, 36, and 1 rows. All passed the existing schema/AST validator and read-only executor. SQL guardrails, timeouts, authorized schema checks, and result-number validation remain independent of Ollama output.

The full suite result was:

```text
92 passed in 54.77s
```

## Files

Added:

- `scripts/benchmark_ollama.py`
- `tests/test_answer_generator.py`
- `evaluation/results/ollama_phase3_before.json`
- `evaluation/results/ollama_phase3_after.json`
- `evaluation/results/ollama_phase3_live_smoke.json`
- `evaluation/results/ollama_phase3_sql_validation.json`
- `evaluation/results/phase3_pytest.xml`

Changed:

- `src/sql_generator.py`
- `src/answer_generator.py`
- `src/retriever.py`
- `src/pipeline.py`
- `src/config.py`
- `.env.example`
- `tests/test_sql_generator.py`
- `tests/test_retriever.py`

## Commands

```powershell
python scripts\benchmark_ollama.py --variant before
python scripts\benchmark_ollama.py --variant after
python -m pytest -q -p no:cacheprovider --basetemp="$env:TEMP\ai-dc-phase3-tests" --junitxml=evaluation\results\phase3_pytest.xml
```

## Interview explanation

The important point is that model persistence alone cannot fix slow CPU inference. The larger practical win came from avoiding an unnecessary second generation. Prompt reduction helped cold latency and token count, but warm inference remained noisy. A failed smaller-context trial was detected through generated-SQL validation and replaced with domain-aware schema inclusion, demonstrating that performance changes were not allowed to reduce correctness.

## Phase decision

Phase 3 is complete. The next optimization is the hybrid router, which can eliminate the remaining SQL-generation call for definitions and common analytical patterns.

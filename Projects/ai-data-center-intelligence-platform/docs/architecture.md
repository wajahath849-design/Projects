# Architecture

```text
External/raw CSVs -> adapter + cleaning -> canonical CSVs -> SQLite + shared KPI layer
                                                        |-> Power BI semantic model
Question -> analyzer -> allow-listed RAG -> local Ollama SQL -> validator -> read-only executor
                                                               -> grounded answer + chart -> CLI/Streamlit
Evaluation corpus ---------------------------------------------> offline/full evaluation only
```

The canonical contract is the boundary between source-specific data and consumers. SQLite provides one reproducible analytical source. Ollama runs locally and receives only allow-listed schema and business metadata, then its proposed SQL is independently parsed and checked before a read-only connection executes it.

Key tradeoffs: SQLite minimizes setup but is single-node; TF-IDF is transparent and sufficient for a small knowledge base but lacks semantic depth; deterministic answer and chart generation reduce hallucination risk but produce less conversational prose. At production scale, use governed warehouse views, identity-aware access control, a model gateway, an embedding index if retrieval quality justifies it, and isolated query workers.

Evaluation ground truth lives under `evaluation/` and is never loaded by `SemanticLayer`.

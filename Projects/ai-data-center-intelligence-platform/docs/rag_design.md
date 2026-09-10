# RAG and Text-to-SQL Design

Production retrieval has a strict allow-list: canonical contract, metric definitions, business glossary, KPI catalog, forecast definitions, reviewed SQL patterns, incident knowledge, runbooks, and error-code documentation. Each chunk carries its source, type, and collection. TF-IDF with word/bigram features ranks chunks within the collections allowed for the current task.

SQL retrieval searches only semantic, forecast, and reviewed-SQL collections before adding exact hinted schema chunks. Investigation retrieval searches only incident knowledge, runbooks, and error-code documentation. Evaluation paths are resolved and rejected before indexing, and an unknown collection returns no results.

The generator uses Ollama's local chat API and requests a structured JSON object containing one SQL string. The prompt treats the user question as untrusted. Generation is not authorization: `SQLValidator` separately enforces SELECT/CTE-only syntax, blocks comments and multiple statements, checks SQLGlot's AST when installed, checks tables/columns, and adds a result limit. Execution uses SQLite `mode=ro`, `query_only`, a progress-handler timeout, and a final row cap.

The Streamlit interface behaves as a conversation rather than a sequence of unrelated prompts. It carries forward the active metric, facility, and year only when the next message looks like a follow-up. Definition-style questions are answered from retrieved allow-listed project knowledge. Analytical questions still generate and execute read-only SQL, and Ollama turns the returned rows into natural language. A numerical validator checks that answer values came from the result or from explicit filters in the user's question; otherwise the UI falls back to the authoritative result table.

"Learning from the data" here means querying the latest SQLite contents and refitting forecast models on every request. The Ollama language model is not retrained when records change, and the project does not claim online learning.

This design limits—but cannot eliminate—LLM risk. Production should add per-user data entitlements, query-cost estimation, model/prompt version tracking, red-team suites, and human-reviewed changes to the semantic layer.

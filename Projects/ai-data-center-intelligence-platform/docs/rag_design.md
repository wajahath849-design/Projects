# RAG and Text-to-SQL Design

Production retrieval has a strict allow-list: canonical contract, metric definitions, business glossary, KPI catalog, and three reviewed SQL patterns. Each chunk carries its source and type. TF-IDF with word/bigram features ranks chunks and passes the top configured items to the SQL generator.

The generator uses Ollama's local chat API and requests a structured JSON object containing one SQL string. The prompt treats the user question as untrusted. Generation is not authorization: `SQLValidator` separately enforces SELECT/CTE-only syntax, blocks comments and multiple statements, checks SQLGlot's AST when installed, checks tables/columns, and adds a result limit. Execution uses SQLite `mode=ro`, `query_only`, a progress-handler timeout, and a final row cap.

This design limits—but cannot eliminate—LLM risk. Production should add per-user data entitlements, query-cost estimation, model/prompt version tracking, red-team suites, and human-reviewed changes to the semantic layer.

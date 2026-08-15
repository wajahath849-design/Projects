# Steps 8–20 Implementation and Verification

## What and why

Steps 8–10 make the system portable and context-aware: external schemas map into one contract, retrieval supplies reviewed business meaning, and question analysis stops irrelevant, unavailable, unsafe, or ambiguous requests early. Steps 11–14 generate, validate, execute, and explain SQL through independent security boundaries. Step 15 exposes the pipeline in Streamlit. Step 16 supplies the Power BI project, shared measures, theme, and page specification. Steps 17–20 add evaluation, tests, and professional documentation.

## Files

Core modules are under `src/`; entry points are `scripts/import_external_dataset.py`, `scripts/ask.py`, and `app/streamlit_app.py`. Evaluation assets are under `evaluation/`. Power BI sources and documentation are under `powerbi/`.

## Commands and expected output

```powershell
ollama pull qwen2.5-coder:7b
python scripts\check_ollama.py
python scripts\import_external_dataset.py C:\path\to\external C:\path\to\canonical --mapping adapters\schema_mapping_template.yaml
python scripts\ask.py "Which facility had the most downtime per server?"
python -m evaluation.evaluate
python -m pytest -q
streamlit run app\streamlit_app.py
```

The importer reports adapted/skipped tables. The terminal prints a grounded answer, validated SQL, and rows. Evaluation prints measured counts. Pytest must pass. Streamlit opens a chat interface with results and technical evidence.

## Common errors

- `Database not found`: run `python scripts\load_database.py`.
- General question has no offline match: start Ollama and run `ollama pull qwen2.5-coder:7b`.
- `No module named ollama/sqlglot/streamlit`: activate the project virtual environment and install requirements.
- External mapping error: add an explicit source-to-canonical mapping in a copied YAML file.
- Power BI refresh error: update the `DataRoot` parameter, refresh tables, and reopen the PBIP rather than saving a failed session.

## Interview preparation

- Why separate generation from validation? The LLM proposes SQL; deterministic code authorizes it.
- Why a canonical model? It prevents every consumer from depending on source filenames and column spellings.
- Why RAG? It supplies current project-specific schema and metric semantics without training a model.
- Why not a vector database? The knowledge set is small; TF-IDF is faster to audit and operate initially.
- Why SQLite? It is reproducible and sufficient for portfolio scale; PostgreSQL or a warehouse is better for concurrency and governed production access.
- How is hallucination controlled? Allow-listed context, strict structured output, schema/AST checks, read-only execution, deterministic answers, and numeric validation.
- What remains a desktop step? Opening, refreshing, visually inspecting, and exporting the Power BI report because `.pbix` is a proprietary desktop artifact.

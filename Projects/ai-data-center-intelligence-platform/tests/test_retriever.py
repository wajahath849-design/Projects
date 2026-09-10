from src.semantic_layer import SemanticLayer
from src.retriever import Retriever


def test_pue_question_retrieves_energy_context():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve("average PUE and cooling power", 5)
    assert any("pue" in item.chunk.text.lower() for item in results)


def test_evaluation_content_never_enters_rag():
    chunks = SemanticLayer(".").build_chunks()
    assert all("evaluation" not in item.metadata.get("source", "") for item in chunks)


def test_sql_retrieval_includes_exact_incident_schema_with_small_top_k():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve_for_sql(
        "Count incidents by facility and root cause", 4
    )
    ids = {item.chunk.chunk_id for item in results}
    assert "schema:uptime_incidents" in ids
    assert "schema:facilities" in ids


def test_sql_retrieval_includes_join_path_for_server_metric():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve_for_sql(
        "Average CPU utilization by facility", 4
    )
    ids = {item.chunk.chunk_id for item in results}
    assert {"schema:server_metrics", "schema:servers", "schema:facilities"} <= ids


def test_incident_retrieval_routes_to_reviewed_operational_collections():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve_for_investigation(
        "TEMP_HIGH and COOL_FLOW_LOW before a cooling outage", 6
    )
    ids = {item.chunk.chunk_id for item in results}
    collections = {item.chunk.metadata["collection"] for item in results}
    assert "incident_knowledge:cooling_failure" in ids
    assert collections <= {"incident_knowledge", "runbooks", "error_codes"}


def test_error_code_retrieval_finds_exact_documentation():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve(
        "What does DEVICE_IO_ERROR mean?", 3, collections={"error_codes"}
    )
    assert results[0].chunk.chunk_id == "error_code:DEVICE_IO_ERROR"


def test_sql_retrieval_excludes_runbook_instructions():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve_for_sql("cooling incident by facility", 4)
    assert all(item.chunk.metadata["collection"] not in {"runbooks", "error_codes"} for item in results)


def test_unknown_collection_returns_no_chunks():
    chunks = SemanticLayer(".").build_chunks()
    assert Retriever(chunks).retrieve("anything", collections={"evaluation"}) == []


def test_exact_error_code_route_searches_only_relevant_collections():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve_error_code("Explain COOL_FLOW_LOW", 4)
    assert results[0].chunk.chunk_id == "error_code:COOL_FLOW_LOW"
    assert all(item.chunk.metadata["collection"] in {"error_codes", "runbooks"} for item in results)

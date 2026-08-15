from src.semantic_layer import SemanticLayer
from src.retriever import Retriever


def test_pue_question_retrieves_energy_context():
    chunks = SemanticLayer(".").build_chunks()
    results = Retriever(chunks).retrieve("average PUE and cooling power", 5)
    assert any("pue" in item.chunk.text.lower() for item in results)


def test_evaluation_content_never_enters_rag():
    chunks = SemanticLayer(".").build_chunks()
    assert all("evaluation" not in item.metadata.get("source", "") for item in chunks)

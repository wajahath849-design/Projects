from pathlib import Path

from src.incident_similarity import IncidentSimilarityEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"


def test_similarity_weights_are_fixed_and_sum_to_one() -> None:
    assert sum(IncidentSimilarityEngine.WEIGHTS.values()) == 1.0


def test_similar_incidents_exclude_query_and_are_sorted() -> None:
    engine = IncidentSimilarityEngine(DATABASE)
    query = engine.profiles()[0]
    results = engine.retrieve(query.incident_id, 5)
    assert len(results) == 5
    assert all(item.incident.incident_id != query.incident_id for item in results)
    assert [item.similarity for item in results] == sorted(
        [item.similarity for item in results], reverse=True
    )
    assert all(0 <= item.similarity <= 1 for item in results)
    assert all(item.incident.resolution for item in results)


def test_signal_search_matches_cooling_history() -> None:
    results = IncidentSimilarityEngine(DATABASE).search_by_signals(
        components=["cooling"],
        log_codes=["TEMP_HIGH", "COOL_FLOW_LOW", "COOLING_INCIDENT"],
        anomaly_metrics=["pue"],
        severity="high",
        top_k=5,
    )
    assert results
    assert any(item.incident.root_cause == "cooling failure" for item in results)
    assert all(item.score_breakdown for item in results)


def test_unknown_similarity_incident_is_rejected() -> None:
    try:
        IncidentSimilarityEngine(DATABASE).retrieve("INC-NOT-REAL")
    except LookupError:
        pass
    else:
        raise AssertionError("Unknown incident should raise LookupError")

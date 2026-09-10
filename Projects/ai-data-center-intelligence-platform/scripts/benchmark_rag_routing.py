"""Benchmark full-corpus retrieval against routed collection retrieval."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import Retriever
from src.semantic_layer import SemanticLayer


CASES = [
    ("What is PUE?", {"kpi_definitions", "glossary"}),
    ("Show average cooling power by facility", {"schema", "kpi_definitions", "sql_examples"}),
    ("What does COOL_FLOW_LOW mean?", {"error_codes", "runbooks"}),
    ("How should I investigate TEMP_HIGH?", {"incident_knowledge", "runbooks", "error_codes"}),
    ("Have we seen a cooling outage before?", {"incident_knowledge", "runbooks"}),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/rag_routing_phase29.json"))
    args = parser.parse_args()
    retriever = Retriever(SemanticLayer(PROJECT_ROOT).build_chunks())
    records = []
    for question, expected in CASES:
        full_samples, routed_samples = [], []
        for _ in range(args.repetitions):
            started = time.perf_counter()
            full = retriever.retrieve(question, 6)
            full_samples.append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            if "COOL_FLOW_LOW" in question:
                routed = retriever.retrieve_error_code(question, 6)
            elif "investigate" in question.lower() or "outage" in question.lower():
                routed = retriever.retrieve_for_investigation(question, 6)
            else:
                routed = retriever.retrieve(
                    question, 6,
                    collections={"schema", "kpi_definitions", "glossary", "sql_examples"},
                )
            routed_samples.append((time.perf_counter() - started) * 1000)
        routed_collections = {item.chunk.metadata["collection"] for item in routed}
        records.append({
            "question": question,
            "expected_collections": sorted(expected),
            "full_collections": sorted({item.chunk.metadata["collection"] for item in full}),
            "routed_collections": sorted(routed_collections),
            "routing_precision": round(
                len(routed_collections & expected) / len(routed_collections), 4
            ) if routed_collections else 0,
            "full_p50_ms": round(statistics.median(full_samples), 4),
            "routed_p50_ms": round(statistics.median(routed_samples), 4),
        })
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repetitions": args.repetitions,
        "collection_sizes": {
            name: len(indexes) for name, indexes in retriever.collection_indexes.items()
        },
        "cases": records,
        "mean_routing_precision": round(statistics.mean(item["routing_precision"] for item in records), 4),
        "full_p50_ms": round(statistics.median(item["full_p50_ms"] for item in records), 4),
        "routed_p50_ms": round(statistics.median(item["routed_p50_ms"] for item in records), 4),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

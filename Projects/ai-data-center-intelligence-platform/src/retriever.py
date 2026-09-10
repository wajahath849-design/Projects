from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.semantic_layer import KnowledgeChunk


@dataclass(frozen=True)
class RetrievalResult:
    chunk: KnowledgeChunk
    score: float


class Retriever:
    SQL_TABLE_HINTS = {
        "facilities": (r"\bfacilit", r"\bsite\b", r"data[ -]?center", r"frankfurt|dublin|ashburn|portland|singapore|sydney"),
        "servers": (r"\bserver", r"server type", r"rack"),
        "server_metrics": (r"\bcpu\b", r"\bmemory\b", r"\bdisk\b", r"server utilization"),
        "power_metrics": (r"\bpue\b", r"cooling", r"power draw", r"it load", r"energy"),
        "network_metrics": (r"latency", r"packet loss", r"throughput", r"bandwidth", r"network availability"),
        "uptime_incidents": (r"incident", r"downtime", r"outage", r"root cause", r"severity"),
        "system_logs": (r"\blog", r"event code", r"warning", r"error", r"restart"),
        "alerts": (r"\balert", r"threshold", r"acknowledged"),
        "maintenance_actions": (r"maintenance", r"resolution", r"how was it fixed", r"action taken"),
    }

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks
        self.by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.matrix = self.vectorizer.fit_transform(chunk.text for chunk in chunks)
        self.collection_indexes: dict[str, list[int]] = {}
        for index, chunk in enumerate(chunks):
            collection = chunk.metadata.get("collection", "unclassified")
            self.collection_indexes.setdefault(collection, []).append(index)
        self.collection_models = {}
        for collection, indexes in self.collection_indexes.items():
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            matrix = vectorizer.fit_transform(self.chunks[index].text for index in indexes)
            self.collection_models[collection] = (indexes, vectorizer, matrix)
        self.collection_group_cache: dict[frozenset[str], tuple[list[int], object]] = {}

    def retrieve(
        self,
        question: str,
        top_k: int = 6,
        collections: set[str] | None = None,
    ) -> list[RetrievalResult]:
        if collections is None:
            query = self.vectorizer.transform([question])
            scores = cosine_similarity(query, self.matrix)[0]
            indexes = scores.argsort()[::-1][: max(1, min(top_k, len(self.chunks)))]
            return [RetrievalResult(self.chunks[index], float(scores[index])) for index in indexes]
        # Transform once with the shared vocabulary, then compare only allowed rows.
        # Per-collection vectorizers made small routed searches slower than the full corpus.
        cache_key = frozenset(collections)
        cached = self.collection_group_cache.get(cache_key)
        if cached is None:
            allowed_indexes = sorted({
                index
                for collection in collections
                for index in self.collection_indexes.get(collection, [])
            })
            cached = (allowed_indexes, self.matrix[allowed_indexes])
            self.collection_group_cache[cache_key] = cached
        allowed_indexes, allowed_matrix = cached
        if not allowed_indexes:
            return []
        query = self.vectorizer.transform([question])
        # TF-IDF rows are L2-normalized, so this sparse dot product is cosine similarity.
        scores = (allowed_matrix @ query.T).toarray().ravel()
        local_indexes = scores.argsort()[::-1][: max(1, min(top_k, len(allowed_indexes)))]
        return [
            RetrievalResult(self.chunks[allowed_indexes[local_index]], float(scores[local_index]))
            for local_index in local_indexes
        ]

    def retrieve_for_sql(self, question: str, top_k: int = 4) -> list[RetrievalResult]:
        """Return compact semantic context plus exact schema chunks required by domain hints."""
        ranked = self.retrieve(
            question,
            top_k,
            collections={
                "schema", "kpi_definitions", "glossary",
                "forecast_definitions", "sql_examples",
            },
        )
        selected = {item.chunk.chunk_id: item for item in ranked}
        lower = question.lower()
        table_names = {
            table
            for table, patterns in self.SQL_TABLE_HINTS.items()
            if any(re.search(pattern, lower) for pattern in patterns)
        }
        for item in ranked:
            for table in self.SQL_TABLE_HINTS:
                if table in item.chunk.text:
                    table_names.add(table)
        for table in sorted(table_names):
            chunk = self.by_id.get(f"schema:{table}")
            if chunk is not None and chunk.chunk_id not in selected:
                selected[chunk.chunk_id] = RetrievalResult(chunk, 1.0)
        return list(selected.values())

    def retrieve_for_investigation(
        self, question: str, top_k: int = 6
    ) -> list[RetrievalResult]:
        """Retrieve only reviewed operational knowledge, runbooks, and code docs."""
        collections = {"incident_knowledge", "runbooks"}
        codes = re.findall(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b", question.upper())
        exact = [
            RetrievalResult(self.by_id[f"error_code:{code}"], 1.0)
            for code in codes
            if f"error_code:{code}" in self.by_id
        ]
        if exact:
            operational = self.retrieve(question, top_k, collections=collections)
            selected = {item.chunk.chunk_id: item for item in exact}
            for item in operational:
                selected.setdefault(item.chunk.chunk_id, item)
            return list(selected.values())[:top_k]
        return self.retrieve(
            question,
            top_k,
            collections=collections,
        )

    def retrieve_error_code(
        self, question: str, top_k: int = 4
    ) -> list[RetrievalResult]:
        """Prefer exact event-code documentation, then related runbook context."""
        codes = re.findall(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b", question.upper())
        exact = []
        for code in codes:
            chunk = self.by_id.get(f"error_code:{code}")
            if chunk is not None:
                exact.append(RetrievalResult(chunk, 1.0))
        supplemental = self.retrieve(question, top_k, collections={"runbooks"})
        selected = {item.chunk.chunk_id: item for item in exact}
        for item in supplemental:
            selected.setdefault(item.chunk.chunk_id, item)
        return list(selected.values())[:top_k]

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.semantic_layer import KnowledgeChunk


@dataclass(frozen=True)
class RetrievalResult:
    chunk: KnowledgeChunk
    score: float


class Retriever:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.matrix = self.vectorizer.fit_transform(chunk.text for chunk in chunks)

    def retrieve(self, question: str, top_k: int = 6) -> list[RetrievalResult]:
        query = self.vectorizer.transform([question])
        scores = cosine_similarity(query, self.matrix)[0]
        indexes = scores.argsort()[::-1][: max(1, min(top_k, len(self.chunks)))]
        return [RetrievalResult(self.chunks[index], float(scores[index])) for index in indexes]


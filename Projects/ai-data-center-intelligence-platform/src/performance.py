from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


TIMING_STAGES = (
    "routing_ms",
    "memory_resolution_ms",
    "rag_retrieval_ms",
    "llm_sql_generation_ms",
    "sql_validation_ms",
    "database_execution_ms",
    "answer_generation_ms",
    "chart_generation_ms",
    "forecast_ms",
    "advanced_analytics_ms",
)


@dataclass
class PerformanceTrace:
    """Low-overhead per-request timing collector based on a monotonic clock."""

    upstream_timings: dict[str, float] | None = None
    timings: dict[str, float] = field(init=False)
    llm_calls: int = 0

    def __post_init__(self) -> None:
        self.timings = {stage: 0.0 for stage in TIMING_STAGES}
        for stage, value in (self.upstream_timings or {}).items():
            if stage in self.timings:
                self.timings[stage] += max(0.0, float(value))

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter_ns()
        try:
            yield
        finally:
            self.add_ms(name, (time.perf_counter_ns() - started) / 1_000_000)

    def add_ms(self, name: str, elapsed_ms: float) -> None:
        if name not in self.timings:
            raise KeyError(f"Unknown performance stage: {name}")
        self.timings[name] += max(0.0, float(elapsed_ms))

    def add_trace(self, timings: dict[str, float] | None, llm_calls: int = 0) -> None:
        for name, elapsed_ms in (timings or {}).items():
            if name in self.timings:
                self.add_ms(name, elapsed_ms)
        self.llm_calls += max(0, int(llm_calls))

    def count_llm_call(self) -> None:
        self.llm_calls += 1

    def snapshot(self) -> dict[str, float]:
        return {name: round(value, 3) for name, value in self.timings.items()}

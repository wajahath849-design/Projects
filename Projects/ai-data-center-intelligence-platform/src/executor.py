from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.database import connect_read_only


@dataclass
class ExecutionResult:
    frame: pd.DataFrame
    execution_ms: float
    row_count: int


class QueryTimeoutError(TimeoutError):
    pass


class SQLExecutor:
    def __init__(self, database_path: Path | str, timeout_seconds: float = 5, max_rows: int = 1000) -> None:
        self.database_path = database_path
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows

    def execute(self, sql: str) -> ExecutionResult:
        started = time.perf_counter()
        deadline = started + self.timeout_seconds
        with connect_read_only(self.database_path) as connection:
            connection.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 1000)
            try:
                frame = pd.read_sql_query(sql, connection)
            except sqlite3.OperationalError as error:
                if "interrupted" in str(error).lower():
                    raise QueryTimeoutError(f"Query exceeded {self.timeout_seconds} seconds") from error
                raise
        frame = frame.head(self.max_rows)
        return ExecutionResult(frame, (time.perf_counter() - started) * 1000, len(frame))

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterator
import uuid
import pyodbc

from .config import SQL_SERVER, SQL_DATABASE, SQL_DRIVER

def connection_string(database: str = SQL_DATABASE) -> str:
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=15;"
    )

@contextmanager
def get_connection() -> Iterator[pyodbc.Connection]:
    connection = pyodbc.connect(connection_string())
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def test_connection() -> None:
    with get_connection() as conn:
        row = conn.cursor().execute(
            "SELECT DB_NAME(), @@SERVERNAME, COUNT(*) "
            "FROM dbo.CustomImagePredictions"
        ).fetchone()
    print(f"SQL connection successful: server={row[1]}, database={row[0]}, rows={row[2]}")

def image_name_exists(image_name: str) -> bool:
    with get_connection() as conn:
        row = conn.cursor().execute(
            "SELECT TOP 1 PredictionID FROM dbo.CustomImagePredictions WHERE ImageName = ?",
            image_name,
        ).fetchone()
    return row is not None

def insert_prediction_batch(predictions: list[dict[str, Any]]) -> uuid.UUID:
    if not predictions:
        raise ValueError("No predictions supplied.")

    batch_id = uuid.uuid4()
    query = """
    INSERT INTO dbo.CustomImagePredictions
    (
        BatchID, ImageName, OriginalImagePath, ProcessedImagePath,
        ModelName, ActualDigit, PredictedDigit,
        Confidence, ConfidencePercentage,
        SecondPrediction, SecondConfidence, SecondConfidencePercentage,
        CorrectPrediction, PredictionStatus,
        ProbabilityDigit0, ProbabilityDigit1, ProbabilityDigit2,
        ProbabilityDigit3, ProbabilityDigit4, ProbabilityDigit5,
        ProbabilityDigit6, ProbabilityDigit7, ProbabilityDigit8,
        ProbabilityDigit9, OriginalWidth, OriginalHeight,
        ProcessedWidth, ProcessedHeight, ProcessingTimeMilliseconds,
        PredictionTime
    )
    VALUES
    (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        for p in predictions:
            values = (
                str(batch_id),
                p["ImageName"],
                p.get("OriginalImagePath"),
                p.get("ProcessedImagePath"),
                p["ModelName"],
                p.get("ActualDigit"),
                int(p["PredictedDigit"]),
                float(p["Confidence"]),
                float(p["ConfidencePercentage"]),
                int(p["SecondPrediction"]),
                float(p["SecondConfidence"]),
                float(p["SecondConfidencePercentage"]),
                p.get("CorrectPrediction"),
                p["PredictionStatus"],
                *[float(p[f"ProbabilityDigit{i}"]) for i in range(10)],
                int(p["OriginalWidth"]),
                int(p["OriginalHeight"]),
                28,
                28,
                float(p["ProcessingTimeMilliseconds"]),
                p["PredictionTime"],
            )
            cursor.execute(query, values)
    return batch_id

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

import pyodbc


SQL_SERVER = os.getenv(
    "MNIST_SQL_SERVER",
    r"localhost\SQLEXPRESS",
)

SQL_DATABASE = os.getenv(
    "MNIST_SQL_DATABASE",
    "MNISTAnalytics",
)

SQL_DRIVER = os.getenv(
    "MNIST_SQL_DRIVER",
    "ODBC Driver 18 for SQL Server",
)


def build_connection_string(
    database: str = SQL_DATABASE,
) -> str:
    """Build the SQL Server connection string."""

    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=15;"
    )


def get_connection(
    database: str = SQL_DATABASE,
) -> pyodbc.Connection:
    """Create and return a SQL Server connection."""

    connection_string = build_connection_string(
        database=database,
    )

    try:
        return pyodbc.connect(connection_string)

    except pyodbc.Error as error:
        installed_drivers = pyodbc.drivers()

        raise ConnectionError(
            "\nCould not connect to SQL Server.\n\n"
            f"Server: {SQL_SERVER}\n"
            f"Database: {database}\n"
            f"ODBC driver: {SQL_DRIVER}\n"
            f"Installed drivers: {installed_drivers}\n\n"
            "Check that:\n"
            "1. SQL Server Express is running.\n"
            "2. The MNISTAnalytics database exists.\n"
            "3. The server name matches your SSMS connection.\n"
            "4. The configured ODBC driver is installed.\n\n"
            f"Original error: {error}"
        ) from error


@contextmanager
def database_connection() -> Generator[
    pyodbc.Connection,
    None,
    None,
]:
    """Provide a connection with commit and rollback handling."""

    connection = get_connection()

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def test_connection() -> None:
    """Test connectivity to SQL Server and the prediction table."""

    query = """
        SELECT
            DB_NAME() AS DatabaseName,
            @@SERVERNAME AS ServerName,
            COUNT(*) AS PredictionCount
        FROM dbo.CustomImagePredictions;
    """

    with database_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "SQL Server returned no connection-test result."
        )

    print("\nSQL Server connection successful.")
    print(f"Server: {row.ServerName}")
    print(f"Database: {row.DatabaseName}")
    print(f"Existing prediction rows: {row.PredictionCount}")


def normalize_boolean(
    value: Any,
) -> bool | None:
    """Convert NumPy or Python boolean values safely."""

    if value is None:
        return None

    return bool(value)


def normalize_datetime(
    value: Any,
) -> datetime:
    """Convert supported datetime values for SQL Server."""

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                f"Invalid PredictionTime value: {value}"
            ) from error

    raise TypeError(
        "PredictionTime must be a datetime or ISO datetime string."
    )


def validate_prediction(
    prediction: dict[str, Any],
) -> None:
    """Validate required prediction fields before insertion."""

    required_fields = [
        "ImageName",
        "Model",
        "PredictedDigit",
        "Confidence",
        "ConfidencePercentage",
        "PredictionStatus",
        "PredictionTime",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in prediction
    ]

    if missing_fields:
        raise ValueError(
            "Prediction is missing required fields: "
            + ", ".join(missing_fields)
        )

    predicted_digit = int(
        prediction["PredictedDigit"]
    )

    if predicted_digit not in range(10):
        raise ValueError(
            "PredictedDigit must be between 0 and 9."
        )

    actual_digit = prediction.get("ActualDigit")

    if (
        actual_digit is not None
        and int(actual_digit) not in range(10)
    ):
        raise ValueError(
            "ActualDigit must be between 0 and 9."
        )


def insert_prediction(
    connection: pyodbc.Connection,
    batch_id: uuid.UUID,
    prediction: dict[str, Any],
) -> int:
    """Insert one prediction and return its SQL identity ID."""

    validate_prediction(prediction)

    insert_query = """
        INSERT INTO dbo.CustomImagePredictions
        (
            BatchID,
            ImageName,
            OriginalImagePath,
            ProcessedImagePath,
            ModelName,
            ActualDigit,
            PredictedDigit,
            Confidence,
            ConfidencePercentage,
            SecondPrediction,
            SecondConfidence,
            SecondConfidencePercentage,
            CorrectPrediction,
            PredictionStatus,
            ProbabilityDigit0,
            ProbabilityDigit1,
            ProbabilityDigit2,
            ProbabilityDigit3,
            ProbabilityDigit4,
            ProbabilityDigit5,
            ProbabilityDigit6,
            ProbabilityDigit7,
            ProbabilityDigit8,
            ProbabilityDigit9,
            OriginalWidth,
            OriginalHeight,
            ProcessedWidth,
            ProcessedHeight,
            PredictionTime
        )
        OUTPUT INSERTED.PredictionID
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        );
    """

    values = (
        str(batch_id),
        str(prediction["ImageName"]),
        prediction.get("OriginalImagePath"),
        prediction.get("ProcessedImagePath"),
        str(prediction["Model"]),
        (
            int(prediction["ActualDigit"])
            if prediction.get("ActualDigit") is not None
            else None
        ),
        int(prediction["PredictedDigit"]),
        float(prediction["Confidence"]),
        float(prediction["ConfidencePercentage"]),
        (
            int(prediction["SecondPrediction"])
            if prediction.get("SecondPrediction") is not None
            else None
        ),
        (
            float(prediction["SecondConfidence"])
            if prediction.get("SecondConfidence") is not None
            else None
        ),
        (
            float(
                prediction[
                    "SecondConfidencePercentage"
                ]
            )
            if prediction.get(
                "SecondConfidencePercentage"
            )
            is not None
            else None
        ),
        normalize_boolean(
            prediction.get("CorrectPrediction")
        ),
        str(prediction["PredictionStatus"]),
        float(prediction.get("ProbabilityDigit0", 0.0)),
        float(prediction.get("ProbabilityDigit1", 0.0)),
        float(prediction.get("ProbabilityDigit2", 0.0)),
        float(prediction.get("ProbabilityDigit3", 0.0)),
        float(prediction.get("ProbabilityDigit4", 0.0)),
        float(prediction.get("ProbabilityDigit5", 0.0)),
        float(prediction.get("ProbabilityDigit6", 0.0)),
        float(prediction.get("ProbabilityDigit7", 0.0)),
        float(prediction.get("ProbabilityDigit8", 0.0)),
        float(prediction.get("ProbabilityDigit9", 0.0)),
        (
            int(prediction["OriginalWidth"])
            if prediction.get("OriginalWidth") is not None
            else None
        ),
        (
            int(prediction["OriginalHeight"])
            if prediction.get("OriginalHeight") is not None
            else None
        ),
        int(prediction.get("ProcessedWidth", 28)),
        int(prediction.get("ProcessedHeight", 28)),
        normalize_datetime(
            prediction["PredictionTime"]
        ),
    )

    cursor = connection.cursor()
    cursor.execute(insert_query, values)

    inserted_row = cursor.fetchone()

    if inserted_row is None:
        raise RuntimeError(
            "SQL Server did not return the inserted PredictionID."
        )

    return int(inserted_row[0])


def insert_prediction_batch(
    predictions: list[dict[str, Any]],
    batch_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """
    Insert all predictions in one transaction.

    The Neural Network and CNN results for one image share
    the same BatchID.
    """

    if not predictions:
        raise ValueError(
            "No predictions were provided for database insertion."
        )

    active_batch_id = batch_id or uuid.uuid4()

    inserted_ids: list[int] = []

    with database_connection() as connection:
        for prediction in predictions:
            prediction_id = insert_prediction(
                connection=connection,
                batch_id=active_batch_id,
                prediction=prediction,
            )

            inserted_ids.append(prediction_id)

            print(
                f"Inserted {prediction['Model']} prediction "
                f"with SQL ID {prediction_id}."
            )

    print(
        f"Prediction batch saved successfully: "
        f"{active_batch_id}"
    )

    return active_batch_id


def image_already_processed(
    image_name: str,
) -> bool:
    """Check whether an image name already exists in SQL Server."""

    query = """
        SELECT TOP 1 PredictionID
        FROM dbo.CustomImagePredictions
        WHERE ImageName = ?;
    """

    with database_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            query,
            str(image_name),
        )

        row = cursor.fetchone()

    return row is not None


def get_prediction_count() -> int:
    """Return the number of stored model-prediction rows."""

    query = """
        SELECT COUNT(*)
        FROM dbo.CustomImagePredictions;
    """

    with database_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        return 0

    return int(row[0])


if __name__ == "__main__":
    test_connection()
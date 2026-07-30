import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import connect


def main():
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dbo.HumanReview")
        cursor.execute("DELETE FROM dbo.ClassProbability")
        cursor.execute("DELETE FROM dbo.ModelPrediction")
        cursor.execute("DELETE FROM dbo.SystemEvent")
        cursor.execute("DELETE FROM dbo.ImageBatch")
        conn.commit()
    print("Transactional database data cleared; schema and model registry preserved.")


if __name__ == "__main__":
    main()

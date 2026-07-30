from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config
from app.db import connect
from app.image_ops import save_processed_preview_png


def main() -> None:
    updated = 0
    with connect() as connection:
        cursor = connection.cursor()
        rows = cursor.execute(
            """SELECT BatchID,StoredFileName
               FROM dbo.ImageBatch
               WHERE StoredFileName IS NOT NULL
                 AND ProcessingStatus IN(N'Completed',N'PartialSuccess')"""
        ).fetchall()

        for row in rows:
            source = config.PROCESSED / Path(str(row.StoredFileName)).name
            if not source.is_file():
                continue
            processed_name = f"{row.BatchID}_processed_28x28.png"
            target = config.PROCESSED / processed_name
            save_processed_preview_png(source, target)
            cursor.execute(
                """UPDATE dbo.ImageBatch
                   SET ProcessedFileName=?,
                       ProcessedImageRelativePath=?,
                       ProcessedImageUrl=?
                   WHERE BatchID=?""",
                processed_name,
                f"data/processed/{processed_name}",
                f"{config.PUBLIC_API_BASE_URL}/images/{processed_name}?preview=8x",
                row.BatchID,
            )
            updated += 1

        connection.commit()
    print(f"Backfilled {updated} processed image preview(s).")


if __name__ == "__main__":
    main()

from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.jobs import process_one_job


settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Pipeline worker started")
    while True:
        processed = process_one_job()
        if not processed:
            time.sleep(settings.pipeline_poll_seconds)


if __name__ == "__main__":
    main()

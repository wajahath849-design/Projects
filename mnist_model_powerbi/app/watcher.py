from __future__ import annotations
import shutil
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import (
    ARCHIVE_DIR, FAILED_DIR, INCOMING_DIR,
    PROCESS_EXISTING_ON_START, SKIP_DUPLICATE_NAMES,
    SUPPORTED_EXTENSIONS, ensure_directories
)
from .database import image_name_exists, test_connection
from .logger import get_logger
from .model_loader import ModelBundle
from .predictor import infer_actual_digit, predict_image

logger = get_logger("watcher")

def _wait_until_ready(path: Path, timeout: int = 30) -> bool:
    started = time.time()
    previous = -1
    stable = 0
    while time.time() - started < timeout:
        if not path.exists():
            time.sleep(0.5)
            continue
        try:
            size = path.stat().st_size
            with path.open("rb"):
                pass
        except OSError:
            stable = 0
            time.sleep(0.5)
            continue
        stable = stable + 1 if size > 0 and size == previous else 0
        if stable >= 3:
            return True
        previous = size
        time.sleep(0.5)
    return False

def _unique_destination(folder: Path, name: str) -> Path:
    candidate = folder / name
    if not candidate.exists():
        return candidate
    p = Path(name)
    return folder / f"{p.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}{p.suffix}"

class Processor:
    def __init__(self) -> None:
        self.models = ModelBundle()
        self.active: set[str] = set()
        self.lock = threading.Lock()

    def process(self, path: Path) -> None:
        key = str(path.resolve())
        with self.lock:
            if key in self.active:
                return
            self.active.add(key)
        try:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                return
            if not _wait_until_ready(path):
                raise TimeoutError("File did not become ready.")
            if SKIP_DUPLICATE_NAMES and image_name_exists(path.name):
                logger.warning("Duplicate image skipped: %s", path.name)
                destination = _unique_destination(ARCHIVE_DIR / "duplicates", path.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(destination))
                return

            predict_image(path, self.models, infer_actual_digit(path.name))
            destination = _unique_destination(ARCHIVE_DIR, path.name)
            shutil.move(str(path), str(destination))
            logger.info("Processed and archived: %s", destination)
        except Exception as exc:
            logger.exception("Processing failed for %s: %s", path, exc)
            if path.exists():
                destination = _unique_destination(FAILED_DIR, path.name)
                shutil.move(str(path), str(destination))
        finally:
            with self.lock:
                self.active.discard(key)

class Handler(FileSystemEventHandler):
    def __init__(self, processor: Processor) -> None:
        self.processor = processor

    def _start(self, path: str) -> None:
        threading.Thread(
            target=self.processor.process,
            args=(Path(path),),
            daemon=True,
        ).start()

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._start(event.src_path)

    def on_moved(self, event) -> None:
        if not event.is_directory:
            self._start(event.dest_path)

def run() -> None:
    ensure_directories()
    test_connection()
    processor = Processor()

    if PROCESS_EXISTING_ON_START:
        for path in sorted(INCOMING_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                processor.process(path)

    observer = Observer()
    observer.schedule(Handler(processor), str(INCOMING_DIR), recursive=False)
    observer.start()
    logger.info("Watching: %s", INCOMING_DIR.resolve())
    logger.info("Drop images into this folder. Press Ctrl+C to stop.")

    stop = threading.Event()
    def shutdown(*_args) -> None:
        stop.set()
        observer.stop()

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop.is_set():
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    run()

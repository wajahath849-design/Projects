from __future__ import annotations

import logging
import msvcrt
import signal
import threading
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config

if TYPE_CHECKING:
    from .processor import Processor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(config.LOG_FILE, encoding="utf-8")],
)
logger = logging.getLogger("ai-model-watcher")
SUPPORTED = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
WATCHER_LOCK_FILE = config.LOG_FILE.parent / "watcher.lock"


def acquire_watcher_lock() -> BinaryIO | None:
    lock_file = WATCHER_LOCK_FILE.open("a+b")
    lock_file.seek(0, 2)
    if lock_file.tell() == 0:
        lock_file.write(b"0")
        lock_file.flush()
    lock_file.seek(0)
    try:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock_file.close()
        return None
    return lock_file


def release_watcher_lock(lock_file: BinaryIO) -> None:
    try:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        lock_file.close()


class Handler(FileSystemEventHandler):
    def __init__(self, processor: Processor):
        self.processor = processor
        self.active: set[str] = set()
        self.active_lock = threading.Lock()
        self.process_lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED:
            return
        key = str(path.resolve()).casefold()
        with self.active_lock:
            if key in self.active:
                return
            self.active.add(key)
        threading.Thread(target=self._run, args=(path, key), daemon=True).start()

    def _run(self, path: Path, key: str):
        try:
            with self.process_lock:  # predictable one-image-at-a-time execution
                batch_id = self.processor.process(path)
                logger.info("Processed %s as batch %s", path.name, batch_id)
        except Exception:
            logger.exception("Processing failed for %s", path)
        finally:
            with self.active_lock:
                self.active.discard(key)


def process_existing(processor: Processor) -> None:
    for path in sorted(config.INCOMING.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            try:
                processor.process(path)
            except Exception:
                logger.exception("Startup processing failed for %s", path)


def main() -> None:
    watcher_lock = acquire_watcher_lock()
    if watcher_lock is None:
        logger.error(
            "Another watcher instance is already running; this duplicate instance will exit."
        )
        return

    try:
        from .model_registry import load_models
        from .processor import Processor

        result = load_models()
        logger.info(
            "Loaded models: %s",
            ", ".join(cfg["display_name"] for _, cfg in result.loaded.values())
            or "none",
        )
        for cfg, reason in result.unavailable:
            logger.error("Unavailable enabled model %s: %s", cfg["display_name"], reason)
        processor = Processor(result)
        process_existing(processor)

        handler = Handler(processor)
        observer = Observer()
        observer.schedule(handler, str(config.INCOMING), recursive=False)
        observer.start()
        logger.info("Watching: %s", config.INCOMING)

        stopped = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stopped.set())
        signal.signal(signal.SIGTERM, lambda *_: stopped.set())
        try:
            while not stopped.wait(1.0):
                pass
        finally:
            observer.stop()
            observer.join()
            logger.info("Watcher stopped")
    finally:
        release_watcher_lock(watcher_lock)


if __name__ == "__main__":
    main()

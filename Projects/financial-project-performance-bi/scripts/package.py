"""Build a GitHub-style ZIP without local caches or regenerated intermediates."""
from __future__ import annotations

import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from src.utils.common import ROOT


SKIP_DIRS = {".git", ".testdeps", ".pytest_tmp", ".pytest_cache", ".venv",
             "node_modules", "__pycache__", "staging", "curated"}
SKIP_NAMES = {"cache.abf", "localSettings.json", ".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = {".pyc", ".ndjson", ".db", ".pbix", ".zip"}


def package(destination: Path | None = None) -> Path:
    destination = destination or ROOT.parent / "financial-project-performance-bi.zip"
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for base, directories, files in os.walk(ROOT):
            directories[:] = sorted(name for name in directories if name not in SKIP_DIRS)
            for name in sorted(files):
                path = Path(base) / name
                if name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
                    continue
                archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))
    return destination


if __name__ == "__main__":
    print(package())

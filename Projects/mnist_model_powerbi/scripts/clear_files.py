import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import config


def main():
    removed = 0
    for folder in (config.INCOMING, config.PROCESSED, config.FAILED):
        for path in folder.iterdir():
            if path.is_file() and path.name != ".gitkeep":
                path.unlink(missing_ok=True)
                removed += 1
    print(f"Removed {removed} data file(s).")


if __name__ == "__main__":
    main()

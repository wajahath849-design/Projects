from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import AnalyticsPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the data-center analytics assistant a question.")
    parser.add_argument("question", nargs="+", help="Natural-language analytics question")
    args = parser.parse_args()
    result = AnalyticsPipeline().ask(" ".join(args.question))
    print(result.answer)
    if result.sql:
        print(f"\nSQL:\n{result.sql}")
    if result.frame is not None:
        print(f"\nRows: {len(result.frame)}")
        print(result.frame.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit an Excel override JSON payload to the inventory API")
    parser.add_argument("--payload", required=True, help="Path to the JSON payload written by Excel/VBA")
    parser.add_argument("--api-url", default=os.getenv("INVENTORY_API_URL", "http://localhost:8000"))
    parser.add_argument("--result", required=False, help="Optional path for a JSON result file")
    args = parser.parse_args()

    payload_path = Path(args.payload).expanduser().resolve()
    result_path = Path(args.result).expanduser().resolve() if args.result else payload_path.with_suffix(".result.json")
    result_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        api_key = os.getenv("INVENTORY_API_KEY") or os.getenv("API_KEY")
        if not api_key:
            raise RuntimeError("Set INVENTORY_API_KEY or API_KEY in the Windows user environment")
        payload = json.loads(payload_path.read_text(encoding="utf-8-sig"))
        response = requests.post(
            f"{args.api_url.rstrip('/')}/overrides",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        try:
            response_content = response.json()
        except ValueError:
            response_content = response.text
        result = {
            "http_status": response.status_code,
            "ok": response.ok,
            "response": response_content,
        }
        exit_code = 0 if response.ok else 1
    except Exception as exc:
        result = {
            "http_status": None,
            "ok": False,
            "response": {"error": type(exc).__name__, "message": str(exc)},
        }
        exit_code = 1

    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    stream = sys.stdout if exit_code == 0 else sys.stderr
    print(json.dumps(result, indent=2), file=stream)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

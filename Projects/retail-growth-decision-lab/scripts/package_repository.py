"""Create a reviewed GitHub upload ZIP from staged/tracked project files."""
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().strip("\0").split("\0")
    if not names or names == [""]:
        raise ValueError("Stage the reviewed repository files before packaging")
    for name in names:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"Invalid project file: {name}")
        if any(part in {".venv", "node_modules", ".git", ".npm-cache", "release"} for part in path.relative_to(ROOT).parts):
            raise ValueError(f"Generated/private directory staged: {name}")
        if path.name.startswith(".env") or path.suffix in {".sqlite", ".joblib"} or name.startswith("data/raw/"):
            raise ValueError(f"Local input/environment staged: {name}")
        if path.suffix in {".html", ".md", ".json", ".py", ".js", ".jsx", ".mjs", ".cjs", ".yml"}:
            text = path.read_text(encoding="utf-8")
            if re.search(r"C:[/\\]+Users[/\\]+admin", text, re.I):
                raise ValueError(f"Machine-specific user path in {name}")
            if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)", text):
                raise ValueError(f"Potential credential material in {name}; review without printing the value")
    destination = output / "retail-growth-decision-lab-github.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=False) as archive:
        for name in names:
            archive.write(ROOT / name, "retail-growth-decision-lab/" + name)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity failure")
    info = {"file": destination.name, "files": len(names), "bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "zip_integrity": "passed",
            "excluded": ["raw data", "virtual environments", "node_modules", "local caches", "model binaries", "Git metadata"]}
    (output / "release-manifest.json").write_text(json.dumps(info, indent=2)+"\n")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()

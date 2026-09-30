"""Create local secrets once. Never overwrites an existing environment file."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print(".env already exists; preserved")
else:
    content = (root / ".env.example").read_text(encoding="utf-8")
    for key in ("POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY", "API_TOKEN", "APPROVAL_TOKEN"):
        content = content.replace(f"{key}=\n", f"{key}={secrets.token_hex(32)}\n")
    target.write_text(content, encoding="utf-8")
    print("Created .env with independent random local secrets")

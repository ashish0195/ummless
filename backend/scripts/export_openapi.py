"""Write the OpenAPI document to ../docs/openapi.json.  Usage (from backend/): python scripts/export_openapi.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("ENVIRONMENT", "test")

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> None:
    work = tempfile.mkdtemp(prefix="comlogue-openapi-")
    app = create_app(Settings(environment="test", database_url=f"sqlite:///{work}/o.db", media_dir=f"{work}/m",
                              ai_provider="mock"))
    out = BACKEND.parent / "docs" / "openapi.json"
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"Wrote {out} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()

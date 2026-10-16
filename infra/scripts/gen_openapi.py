"""Write the API's OpenAPI document to packages/shared-types/openapi.json (deterministic).

CI runs this and `openapi-typescript`, then fails if the committed copy differs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from shopnod_api.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "packages" / "shared-types" / "openapi.json"

if __name__ == "__main__":
    spec = create_app().openapi()
    OUT.write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(spec['paths'])} paths)")

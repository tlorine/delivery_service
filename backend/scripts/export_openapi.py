"""Write the OpenAPI contract to backend/openapi.json (or --check that it is up to date)."""

import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

TARGET = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> int:
    spec = create_app(Settings(environment="test")).openapi()
    rendered = json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text() != rendered:
            print("openapi.json is outdated: run `uv run python scripts/export_openapi.py`", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(rendered)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

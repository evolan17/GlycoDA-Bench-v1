from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_json_log(path: str, payload: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(p)

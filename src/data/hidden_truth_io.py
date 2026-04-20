"""Write evaluator-only ground truth outside agent-visible case folders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def private_hidden_truth_path(dataset_case_dir: Path) -> Path:
    """Path where ground truth JSON is stored (sibling `_private_hidden_truth/`)."""
    root = Path(dataset_case_dir).resolve()
    return root.parent / "_private_hidden_truth" / f"{root.name}.json"


def write_hidden_truth_for_dataset(dataset_case_dir: Path, payload: dict[str, Any]) -> Path:
    """Persist hidden truth next to the pack (not inside the case dir). Agents only see abundance/metadata."""
    out = private_hidden_truth_path(dataset_case_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

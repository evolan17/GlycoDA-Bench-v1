"""Align glycoforge_metadata.json missingness block with the shipped abundance matrix."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def sync_missingness_with_abundance(glycoforge_metadata_path: Path, abundance_df: pd.DataFrame) -> None:
    if not glycoforge_metadata_path.is_file():
        return
    feat_id = "glycan_index" if "glycan_index" in abundance_df.columns else None
    if feat_id:
        num = abundance_df.drop(columns=[feat_id]).apply(pd.to_numeric, errors="coerce")
    else:
        num = abundance_df.apply(pd.to_numeric, errors="coerce")
    total_nan = int(num.isna().sum().sum())
    size = int(num.size)
    mf_actual = float(total_nan / max(size, 1))
    meta = json.loads(glycoforge_metadata_path.read_text(encoding="utf-8"))
    qc = meta.setdefault("quality_checks", {})
    miss = qc.setdefault("missingness", {})
    if isinstance(miss, dict):
        miss["total_missing"] = total_nan
        miss["missing_fraction_actual"] = mf_actual
        miss["aligned_to_contract_abundance"] = True
    glycoforge_metadata_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

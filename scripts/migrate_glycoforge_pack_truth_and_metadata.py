#!/usr/bin/env python3
"""One-off migration for GlycoForge benchmark packs (648-style).

1. Moves ``gf_case_*/hidden_truth.json`` → ``<pack>/_private_hidden_truth/<case>.json`` so agent-visible
   case dirs no longer contain evaluator ground truth (see ``resolve_hidden_truth_path``).
2. Aligns ``glycoforge_metadata.json`` missingness block with ``abundance.csv`` (same as generator sync).
3. Optionally patches ``manifest.json`` schema (matrix layout) and ``clr_transform`` tool blurb in ``available_tools``.

Usage (from repo root)::

    python scripts/migrate_glycoforge_pack_truth_and_metadata.py data/glycoforge_benchmark_648 --apply
    python scripts/migrate_glycoforge_pack_truth_and_metadata.py data/glycoforge_benchmark_648 --apply --patch-manifest

Dry-run (default): omit ``--apply`` to only print planned actions.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.data.glycoforge_metadata_sync import sync_missingness_with_abundance  # noqa: E402
from src.tools.registry import export_tool_specs_for_manifest  # noqa: E402


def _patch_manifest(manifest: dict) -> dict:
    """Merge matrix semantics; refresh clr_transform description from registry."""
    specs = {s["name"]: s for s in export_tool_specs_for_manifest()}
    tools = manifest.get("available_tools")
    if isinstance(tools, list):
        for i, t in enumerate(tools):
            if isinstance(t, dict) and t.get("name") == "clr_transform" and "clr_transform" in specs:
                tools[i] = dict(specs["clr_transform"])
    schema = manifest.get("schema")
    if not isinstance(schema, dict):
        schema = {}
    schema.update(
        {
            "matrix_layout": "glycans_as_rows_samples_as_columns",
            "feature_row_id_column": "glycan_index",
            "feature_metadata_id_columns": ["glycan_index", "glycan_id"],
            "samples_are_rows_default": False,
        },
    )
    manifest["schema"] = schema
    ds = manifest.get("dataset_summary")
    if isinstance(ds, dict):
        ds["matrix_layout"] = "glycans_as_rows_samples_as_columns"
    return manifest


def _patch_task_json(task: dict) -> dict:
    schema = task.get("schema")
    if not isinstance(schema, dict):
        schema = {}
    schema.update(
        {
            "matrix_layout": "glycans_as_rows_samples_as_columns",
            "feature_row_id_column": "glycan_index",
            "feature_metadata_id_columns": ["glycan_index", "glycan_id"],
            "samples_are_rows_default": False,
        },
    )
    task["schema"] = schema
    return task


def _ensure_feature_metadata_glycan_index(ds_dir: Path, *, apply: bool) -> None:
    fmp = ds_dir / "feature_metadata.csv"
    if not fmp.is_file():
        return
    df = pd.read_csv(fmp)
    if "glycan_index" in df.columns:
        return
    if "glycan_id" not in df.columns:
        return
    df.insert(0, "glycan_index", df["glycan_id"])
    if apply:
        df.to_csv(fmp, index=False)
        print(f"PATCH feature_metadata.csv {ds_dir.name} (glycan_index alias)")
    else:
        print(f"PLAN add glycan_index column from glycan_id ({ds_dir.name})")


def migrate_pack(pack_root: Path, *, apply: bool, patch_manifest: bool) -> None:
    pack_root = pack_root.resolve()
    private_dir = pack_root / "_private_hidden_truth"
    cases = sorted(p for p in pack_root.glob("gf_case_*") if p.is_dir())
    if not cases:
        print(f"No gf_case_* dirs under {pack_root}", file=sys.stderr)
        sys.exit(2)

    for ds_dir in cases:
        ht_in_case = ds_dir / "hidden_truth.json"
        ht_private = private_dir / f"{ds_dir.name}.json"
        if ht_in_case.is_file():
            if apply:
                private_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(ht_in_case), str(ht_private))
                print(f"MOVED truth {ds_dir.name} -> {ht_private.relative_to(pack_root)}")
            else:
                print(f"PLAN move  {ht_in_case} -> {ht_private}")

        abundance = ds_dir / "abundance.csv"
        gmeta = ds_dir / "glycoforge_metadata.json"
        if abundance.is_file() and gmeta.is_file():
            df = pd.read_csv(abundance)
            if apply:
                sync_missingness_with_abundance(gmeta, df)
                print(f"SYNC  glycoforge_metadata missingness {ds_dir.name}")
            else:
                print(f"PLAN sync glycoforge_metadata.json from abundance.csv ({ds_dir.name})")

        _ensure_feature_metadata_glycan_index(ds_dir, apply=apply)

        tpath = ds_dir / "task.json"
        if tpath.is_file():
            task = json.loads(tpath.read_text(encoding="utf-8"))
            task = _patch_task_json(task)
            if apply:
                tpath.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"PATCH task.json {ds_dir.name}")
            else:
                print(f"PLAN patch task.json (matrix schema) {ds_dir.name}")

        if patch_manifest:
            mpath = ds_dir / "manifest.json"
            if not mpath.is_file():
                continue
            man = json.loads(mpath.read_text(encoding="utf-8"))
            new_man = _patch_manifest(man)
            if apply:
                mpath.write_text(json.dumps(new_man, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"PATCH manifest.json {ds_dir.name}")
            else:
                print(f"PLAN patch manifest.json (matrix schema + clr tool) {ds_dir.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack_root", type=Path, help="Pack root, e.g. data/glycoforge_benchmark_648")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Perform moves and writes; default is dry-run.",
    )
    ap.add_argument(
        "--patch-manifest",
        action="store_true",
        help="Also update manifest schema + clr_transform tool description.",
    )
    args = ap.parse_args()
    migrate_pack(args.pack_root, apply=args.apply, patch_manifest=args.patch_manifest)
    if not args.apply:
        print("\nDry-run only. Re-run with --apply to execute.", file=sys.stderr)


if __name__ == "__main__":
    main()

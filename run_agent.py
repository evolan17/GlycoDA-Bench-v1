from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from src.config import apply_api_runtime_config, load_api_runtime_config

from glycoagentbench.agent_core import plan_workflow_with_agent
from glycoagentbench.data_io import generate_glycoforge_synthetic, import_csv_data
from glycoagentbench.executor import execute_workflow, has_batch_effect
from glycoagentbench.metrics import score_run
from glycoagentbench.visualize import draw_workflow_dag


def _de_result_path(exec_steps: list[dict]) -> str:
    for s in exec_steps:
        if s["tool"] == "differential_analysis":
            return s["output"]
    raise RuntimeError("workflow does not contain differential_analysis")


def _last_matrix_path(exec_steps: list[dict], raw_features: str) -> str:
    current = raw_features
    for s in exec_steps:
        if s["tool"] != "differential_analysis":
            current = s["output"]
    return current


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run LangChain agent glycomics workflow benchmark")
    p.add_argument("--mode", choices=["synthetic", "csv"], default="synthetic")
    p.add_argument("--scenario", default="synthetic")
    p.add_argument("--features-csv", default="")
    p.add_argument("--meta-csv", default="")
    p.add_argument("--labels-csv", default="")
    p.add_argument("--out-dir", default="outputs")
    p.add_argument("--n-samples", type=int, default=120)
    p.add_argument("--n-features", type=int, default=60)
    p.add_argument("--seeds", default="42,43,44")
    p.add_argument("--biostrength", type=float, default=1.0)
    p.add_argument("--batch-strength", type=float, default=1.0)
    p.add_argument("--missingness-bias", type=float, default=0.08)
    p.add_argument("--templated", action="store_true")
    p.add_argument("--include-motif", action="store_true")
    p.add_argument("--model", default="openai:gpt-4.1")
    p.add_argument("--require-llm", action="store_true")
    p.add_argument("--api-config", default="configs/api.yaml")
    return p.parse_args()


def _prepare_csv_input(features_csv: str, meta_csv: str, labels_csv: str, out_dir: Path) -> tuple[str, str]:
    x, meta = import_csv_data(features_csv, meta_csv)
    if labels_csv:
        labels = pd.read_csv(labels_csv)
        if "sample_id" not in labels.columns or "label" not in labels.columns:
            raise ValueError("labels csv must contain sample_id,label")
        meta = meta.drop(columns=["label"], errors="ignore").merge(labels[["sample_id", "label"]], on="sample_id")
    inp = out_dir / "input"
    inp.mkdir(parents=True, exist_ok=True)
    x_path = inp / "features.csv"
    m_path = inp / "meta.csv"
    x.to_csv(x_path, index=False)
    meta.to_csv(m_path, index=False)
    return str(x_path), str(m_path)


def run_once(args: argparse.Namespace, seed: int, run_root: Path) -> dict:
    run_dir = run_root / f"seed_{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "synthetic":
        bundle = generate_glycoforge_synthetic(
            out_dir=str(run_dir / "data"),
            n_samples=args.n_samples,
            n_features=args.n_features,
            seed=seed,
            biostrength=args.biostrength,
            batch_strength=args.batch_strength,
            missing_bias=args.missingness_bias,
            templated=args.templated,
        )
        features_csv, meta_csv, ground_truth = (
            str(bundle.features_csv),
            str(bundle.meta_csv),
            str(bundle.ground_truth_json) if bundle.ground_truth_json else None,
        )
    else:
        features_csv, meta_csv = _prepare_csv_input(args.features_csv, args.meta_csv, args.labels_csv, run_dir)
        ground_truth = None

    prompt = (
        f"Scenario={args.scenario}; seed={seed}; biostrength={args.biostrength}; "
        f"batch_strength={args.batch_strength}; missingness_bias={args.missingness_bias}"
    )
    plan = plan_workflow_with_agent(
        prompt,
        has_batch=has_batch_effect(meta_csv),
        include_motif=args.include_motif,
        model=args.model,
        require_llm=args.require_llm,
    )
    exec_result = execute_workflow(plan, features_csv=features_csv, meta_csv=meta_csv, run_dir=str(run_dir / "workflow"))

    de_csv = _de_result_path(exec_result.step_outputs)
    processed_csv = _last_matrix_path(exec_result.step_outputs, features_csv)
    metrics = score_run(
        raw_features_csv=features_csv,
        processed_features_csv=processed_csv,
        de_csv=de_csv,
        meta_csv=meta_csv,
        ground_truth_json=ground_truth,
    )

    dag_png = draw_workflow_dag(plan, str(run_dir / "workflow_dag.png"))
    report = {
        "seed": seed,
        "plan": plan,
        "execution_log": exec_result.log_path,
        "dag_png": dag_png,
        "metrics": metrics,
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    # Auto-load project-level .env (does not override already-exported env vars).
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)
    args = parse_args()
    apply_api_runtime_config(load_api_runtime_config(args.api_config))
    if args.model == "openai:gpt-4.1" and os.getenv("GLYCOAGENT_MODEL"):
        args.model = os.environ["GLYCOAGENT_MODEL"]
    run_root = Path(args.out_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    reports = [run_once(args, seed=s, run_root=run_root) for s in seeds]
    summary = {
        "n_runs": len(reports),
        "overall_score_mean": sum(r["metrics"]["overall_score"] for r in reports) / max(len(reports), 1),
        "runs": reports,
    }
    (run_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Done. Summary: {run_root / 'summary.json'}")


if __name__ == "__main__":
    main()

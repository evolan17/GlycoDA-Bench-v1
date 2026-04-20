from __future__ import annotations

from pathlib import Path

from glycoagentbench.agent_core import plan_workflow_with_agent
from glycoagentbench.data_io import generate_glycoforge_synthetic
from glycoagentbench.executor import execute_workflow, has_batch_effect
from glycoagentbench.metrics import score_run


def test_smoke_pipeline(tmp_path: Path):
    bundle = generate_glycoforge_synthetic(str(tmp_path / "data"), n_samples=30, n_features=20, seed=7)
    plan = plan_workflow_with_agent("smoke", has_batch=has_batch_effect(str(bundle.meta_csv)))
    result = execute_workflow(plan, str(bundle.features_csv), str(bundle.meta_csv), str(tmp_path / "run"))
    de_csv = [s["output"] for s in result.step_outputs if s["tool"] == "differential_analysis"][0]
    proc_csv = [s["output"] for s in result.step_outputs if s["tool"] != "differential_analysis"][-1]
    scores = score_run(
        raw_features_csv=str(bundle.features_csv),
        processed_features_csv=proc_csv,
        de_csv=de_csv,
        meta_csv=str(bundle.meta_csv),
        ground_truth_json=str(bundle.ground_truth_json),
    )
    assert "overall_score" in scores

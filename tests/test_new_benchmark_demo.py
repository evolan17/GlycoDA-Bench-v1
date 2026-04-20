from __future__ import annotations

from src.config import load_model_config
from src.data.dataset import build_planner_context, load_dataset_paths, summarize_dataset
from src.llm.adapter import LLMAdapter
from src.planner.planner import plan_workflow
from src.tools.registry import list_tool_names


def test_mock_planner_outputs_structured_plan():
    cfg = load_model_config("configs/models/mock.yaml")
    adapter = LLMAdapter(cfg)
    paths = load_dataset_paths("data/mock_demo")
    summary = summarize_dataset(paths)
    ctx = build_planner_context(summary)
    plan = plan_workflow(adapter, ctx, list_tool_names(), ["test"])
    assert plan.workflow_name
    assert len(plan.steps) > 0
    assert all(step.tool for step in plan.steps)

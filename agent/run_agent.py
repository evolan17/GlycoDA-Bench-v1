from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_root_main():
    root_run_agent = Path(__file__).resolve().parents[1] / "run_agent.py"
    spec = importlib.util.spec_from_file_location("root_run_agent", root_run_agent)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load root run_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


if __name__ == "__main__":
    main = _load_root_main()
    main()

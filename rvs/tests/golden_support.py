"""Shared by tests/test_golden.py and scripts/gen_goldens.py."""

from datetime import datetime
from pathlib import Path

from rvs_core.config import load_project_config
from rvs_core.exporters.catalog import all_outputs
from rvs_core.matrices import Provenance
from rvs_core.validate import validate_project

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
EXAMPLES = ROOT / "examples"


def outputs_for(name: str) -> dict[str, bytes]:
    project = EXAMPLES / name
    report = validate_project(project, doorstop=False)
    cfg, _ = load_project_config(project)
    assert report.graph is not None
    prov = Provenance("0.1.0", "3.2", cfg.project.name, "working copy", datetime(2026, 1, 2, 3, 4, 5), "golden")
    return all_outputs(cfg, report.items, report.graph, prov, trace=("SYS", "EPS", "down"), impact_uid="SYS-0002")

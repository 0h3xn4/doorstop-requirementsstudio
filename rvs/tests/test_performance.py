"""Performance targets (spec): open 5,000 items < 3 s, matrix generation < 5 s. Run with: pytest -m perf.

The stress project takes about a minute to generate; set RVS_STRESS_DIR to reuse one between runs.
"""

import os
import shutil
import time
from pathlib import Path

import pytest

from rvs_core.config import load_project_config
from rvs_core.examples.stress import build_stress_project
from rvs_core.matrices import Provenance, VcmFilter, build_traceability, build_vcm
from rvs_core.trace import LinkGraph, coverage, impact
from rvs_core.validate import validate_project

pytestmark = pytest.mark.perf


@pytest.fixture(scope="module")
def stress(tmp_path_factory: pytest.TempPathFactory) -> Path:
    shared = os.environ.get("RVS_STRESS_DIR")
    root = Path(shared) / "stress5000" if shared else tmp_path_factory.mktemp("stress") / "stress5000"
    if not (root / "rvs-project.yaml").exists():
        build_stress_project(root, 5000)
    # age the files so the cache is allowed to store them, then start from a cold cache
    old = time.time() - 600
    for p in root.rglob("*.yml"):
        os.utime(p, (old, old))
    shutil.rmtree(root / ".rvs-cache", ignore_errors=True)
    return root


def test_warm_open_under_three_seconds(stress: Path):
    validate_project(stress, doorstop=False)  # first run fills the cache
    t = time.perf_counter()
    report = validate_project(stress, doorstop=False)
    elapsed = time.perf_counter() - t
    print(f"\nwarm open + rules + links: {elapsed:.2f} s ({len(report.items)} items)")
    assert len(report.items) == 5000
    assert elapsed < 3.0


def test_matrices_under_five_seconds(stress: Path):
    report = validate_project(stress, doorstop=False)
    cfg, _ = load_project_config(stress)
    prov = Provenance.now(cfg, user="perf")
    t = time.perf_counter()
    graph = LinkGraph.build(cfg, report.items)
    vcm = build_vcm(cfg, report.items, graph, VcmFilter(), provenance=prov)
    trace = build_traceability(cfg, report.items, graph, "SYS", "EPS", "down", provenance=prov)
    cov = coverage(cfg, report.items, graph)
    impact(graph, "SYS-0001")
    elapsed = time.perf_counter() - t
    print(f"\ngraph + VCM ({len(vcm.rows)} rows) + trace ({len(trace.rows)}) + coverage: {elapsed:.2f} s")
    assert cov and elapsed < 5.0


def test_cold_open_is_reported(stress: Path):
    shutil.rmtree(stress / ".rvs-cache", ignore_errors=True)
    t = time.perf_counter()
    validate_project(stress, doorstop=False)
    print(f"\ncold open (no cache): {time.perf_counter() - t:.2f} s")

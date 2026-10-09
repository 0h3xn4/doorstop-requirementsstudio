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


def test_export_and_import_timings_at_5000_items(stress: Path):
    """Reported, not asserted tightly: exports run on a worker thread in the GUI. Only a generous ceiling is enforced."""
    from rvs_core.exporters import render_doc, render_table
    from rvs_core.exporters.builders import spec_doc
    from rvs_core.exporters.itemsio import (
        export_items_csv,
        export_items_xlsx,
        plan_import,
        read_csv,
        read_xlsx,
    )

    report = validate_project(stress, doorstop=False)
    cfg, _ = load_project_config(stress)
    prov = Provenance.now(cfg, user="perf")
    graph = report.graph
    assert graph is not None
    timings: dict[str, float] = {}

    def timed(name: str, fn):  # type: ignore[no-untyped-def]
        t = time.perf_counter()
        out = fn()
        timings[name] = time.perf_counter() - t
        return out

    csv_bytes = timed("items csv export", lambda: export_items_csv(cfg, report.items, prov))
    xlsx_bytes = timed("items xlsx export", lambda: export_items_xlsx(cfg, report.items, prov))
    rows = timed("items csv read", lambda: read_csv(csv_bytes))
    timed("items xlsx read", lambda: read_xlsx(xlsx_bytes))
    plan = timed("import plan (5000 rows)", lambda: plan_import(cfg, report.items, rows))
    assert plan.count("unchanged") == 5000
    vcm = build_vcm(cfg, report.items, graph, VcmFilter(), provenance=prov)
    for fmt in ("xlsx", "html", "docx", "pdf"):
        timed(f"vcm {fmt} ({len(vcm.rows)} rows)", lambda fmt=fmt: render_table(vcm, fmt))
    spec = spec_doc(cfg, report.items, graph, None, prov)
    for fmt in ("html", "docx", "pdf"):
        timed(f"spec {fmt} (5000 items)", lambda fmt=fmt: render_doc(spec, fmt))
    for name, seconds in timings.items():
        print(f"\n{name:34} {seconds:6.1f} s")
    assert max(timings.values()) < 300


def test_baseline_and_diff_timings_at_5000_items(stress: Path, tmp_path: Path):
    """A baseline commits and tags all 5,000 items; a diff extracts and parses the tagged tree (cold)."""
    from rvs_core.authoring import EditService
    from rvs_core.changecontrol.baselines import create_baseline, verify_baseline
    from rvs_core.changecontrol.diff import diff_snapshots, load_snapshot
    from rvs_core.vcs.git import GitRepo

    root = tmp_path / "stress"
    shutil.copytree(stress, root, ignore=shutil.ignore_patterns(".rvs-cache"))
    old = time.time() - 600
    for p in root.rglob("*.yml"):
        os.utime(p, (old, old))
    GitRepo.init(root)
    timings: dict[str, float] = {}

    def timed(name: str, fn):  # type: ignore[no-untyped-def]
        t = time.perf_counter()
        out = fn()
        timings[name] = time.perf_counter() - t
        return out

    timed("baseline create (5000 items)", lambda: create_baseline(root, "B1", "perf", user="perf"))
    EditService(root, user="perf").update_item("SYS-0001", attrs={"owner": "changed"}, why="perf")
    timed("verify (deep, cold extract)", lambda: verify_baseline(root, "B1"))
    base = timed("load baseline snapshot (warm)", lambda: load_snapshot(root, "B1"))
    work = timed("load working copy", lambda: load_snapshot(root, None))
    diff = timed("diff 5000 vs 5000", lambda: diff_snapshots(base, work))
    assert diff.changed == 1
    for name, seconds in timings.items():
        print(f"\n{name:34} {seconds:6.1f} s")
    assert max(timings.values()) < 120

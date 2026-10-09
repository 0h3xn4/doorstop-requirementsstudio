from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.matrices import VcmFilter, aggregate_status, build_traceability, build_vcm
from rvs_core.matrices.provenance import Provenance
from rvs_core.trace import LinkGraph

PROV = Provenance(tool_version="0.0", framework_version="3.2", project="P", baseline="working copy",
                  generated=datetime(2026, 1, 2, 3, 4, 5), user="alice")  # fmt: skip


def _ctx(root: Path) -> tuple[Any, Any, Any]:
    cfg, _ = load_project_config(root)
    items = DoorstopProject.open(root).items()
    return cfg, items, LinkGraph.build(cfg, items)


def _rows(table: Any) -> dict[str, list[str]]:
    return {r[0]: r for r in table.rows}


# traceability matrix ----------------------------------------------------------
def test_trace_down_lists_children_and_flags_childless(minimal_project: Path):
    DoorstopProject.open(minimal_project).add_item("SYS", "The spacecraft shall be lonely.", attrs={"title": "Lonely"})
    cfg, items, graph = _ctx(minimal_project)
    t = build_traceability(cfg, items, graph, "SYS", "EPS", "down", provenance=PROV)
    rows = _rows(t)
    assert set(rows) == {"SYS-0001", "SYS-0002", "SYS-0003", "SYS-0005"}  # heading SYS-0004 is not normative
    assert rows["SYS-0002"][t.columns.index("Linked items")] == "EPS-0001"
    assert t.flags[t.rows.index(rows["SYS-0005"])] == "childless"
    assert t.flags[t.rows.index(rows["SYS-0001"])] is None


def test_trace_up_lists_parents_and_flags_orphans(minimal_project: Path):
    DoorstopProject.open(minimal_project).add_item("EPS", "The EPS shall be orphaned.", attrs={"title": "Orphan"})
    cfg, items, graph = _ctx(minimal_project)
    t = build_traceability(cfg, items, graph, "EPS", "SYS", "up", provenance=PROV)
    rows = _rows(t)
    assert rows["EPS-0001"][t.columns.index("Linked items")] == "SYS-0002"
    assert t.flags[t.rows.index(rows["EPS-0004"])] == "orphan"


def test_trace_to_verification_document_flags_unverified(minimal_project: Path):
    DoorstopProject.open(minimal_project).add_item(
        "EPS", "The EPS shall be unverified.", attrs={"title": "U", "status": "approved"}
    )
    cfg, items, graph = _ctx(minimal_project)
    t = build_traceability(cfg, items, graph, "EPS", "VER", "down", provenance=PROV)
    rows = _rows(t)
    assert rows["EPS-0001"][t.columns.index("Linked items")] == "VER-0001"
    assert t.flags[t.rows.index(rows["EPS-0004"])] == "unverified-approved"
    assert t.flags[t.rows.index(rows["EPS-0003"])] is None


def test_trace_includes_typed_links_and_link_types(minimal_project: Path):
    DoorstopProject.open(minimal_project).update_item("EPS-0001", attrs={"link_satisfies": ["SYS-0001"]})
    cfg, items, graph = _ctx(minimal_project)
    t = build_traceability(cfg, items, graph, "EPS", "SYS", "up", provenance=PROV)
    row = _rows(t)["EPS-0001"]
    assert row[t.columns.index("Linked items")] == "SYS-0001, SYS-0002"
    assert row[t.columns.index("Link types")] == "parent, satisfies"


def test_trace_unknown_document_is_an_error(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    with pytest.raises(ValueError, match="NOPE"):
        build_traceability(cfg, items, graph, "NOPE", "SYS", "down", provenance=PROV)


# VCM ---------------------------------------------------------------------------
def test_aggregate_status_convention():
    assert aggregate_status([]) == "not verified"
    assert aggregate_status(["passed", "passed"]) == "passed"
    assert aggregate_status(["passed", "failed"]) == "failed"
    assert aggregate_status(["waived", "waived"]) == "waived"
    assert aggregate_status(["planned"]) == "planned"
    assert aggregate_status(["passed", "planned"]) == "in-progress"
    assert aggregate_status(["in-progress", "planned"]) == "in-progress"


def test_vcm_has_one_row_per_normative_requirement(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    t = build_vcm(cfg, items, graph, provenance=PROV)
    rows = _rows(t)
    assert set(rows) == {"SYS-0001", "SYS-0002", "SYS-0003", "EPS-0001", "EPS-0002", "EPS-0003"}
    col = {c: i for i, c in enumerate(t.columns)}
    assert rows["EPS-0001"][col["Verification item"]] == "VER-0001"
    assert rows["EPS-0001"][col["Method"]] == "analysis"
    assert rows["EPS-0001"][col["Status"]] == "planned"
    assert rows["SYS-0001"][col["Verification item"]] == ""
    assert rows["SYS-0001"][col["Status"]] == "not verified"


def test_vcm_aggregates_evidence_and_status(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    proj.update_item("VER-0001", attrs={"v_status": "passed", "evidence": "reports/eps-a.pdf"})
    proj.add_item("VER", "Second check.", attrs={"title": "2", "verify_method": "analysis", "verify_level": "system",
                  "v_status": "failed", "evidence": "reports/eps-b.pdf", "link_verifies": ["EPS-0001"]}, derived=True)  # fmt: skip
    cfg, items, graph = _ctx(minimal_project)
    t = build_vcm(cfg, items, graph, provenance=PROV)
    row = _rows(t)["EPS-0001"]
    col = {c: i for i, c in enumerate(t.columns)}
    assert row[col["Verification item"]] == "VER-0001, VER-0004"
    assert row[col["Status"]] == "failed"
    assert row[col["Evidence"]] == "reports/eps-a.pdf; reports/eps-b.pdf"


def test_vcm_filters(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    only_eps = build_vcm(cfg, items, graph, VcmFilter(documents=("EPS",)), provenance=PROV)
    assert {r[0] for r in only_eps.rows} == {"EPS-0001", "EPS-0002", "EPS-0003"}
    tests = build_vcm(cfg, items, graph, VcmFilter(methods=("test",)), provenance=PROV)
    assert {r[0] for r in tests.rows} == {"SYS-0002", "EPS-0002"}
    gaps = build_vcm(cfg, items, graph, VcmFilter(only_gaps=True), provenance=PROV)
    assert {r[0] for r in gaps.rows} == {"SYS-0001", "SYS-0002", "SYS-0003"}  # nothing verifies them
    planned = build_vcm(cfg, items, graph, VcmFilter(statuses=("planned",)), provenance=PROV)
    assert {r[0] for r in planned.rows} == {"EPS-0001", "EPS-0002", "EPS-0003"}


def test_vcm_columns_come_from_configuration(minimal_project: Path):
    import yaml

    path = minimal_project / "config" / "exports.yaml"
    data = yaml.safe_load(path.read_text())
    data["vcm"]["columns"] = [{"key": "uid", "title": "Req"}, {"key": "verify_method", "title": "How"}]
    path.write_text(yaml.safe_dump(data))
    cfg, items, graph = _ctx(minimal_project)
    t = build_vcm(cfg, items, graph, provenance=PROV)
    assert t.columns == ["Req", "How"]


def test_vcm_carries_provenance_and_placeholder_note(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    t = build_vcm(cfg, items, graph, provenance=PROV)
    assert t.provenance == PROV
    assert t.notes and "TODO-STANDARD" in " ".join(t.notes)  # layout is not yet ECSS-conformant
    assert PROV.lines()[0].startswith("Project: P")
    assert "2026-01-02" in " ".join(PROV.lines()) and "alice" in " ".join(PROV.lines())


def test_matrices_are_deterministic(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    a = build_vcm(cfg, items, graph, provenance=PROV)
    b = build_vcm(cfg, items, graph, provenance=PROV)
    assert a == b

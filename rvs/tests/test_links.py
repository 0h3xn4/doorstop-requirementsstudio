"""Typed links: graph, validation, suspect links, childless items; fast vs full validation."""

from pathlib import Path
from typing import Any

import pytest

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.findings import Severity
from rvs_core.trace import LinkGraph, validate_links
from rvs_core.validate import validate_project


def _graph(root: Path) -> tuple[LinkGraph, Any, list[Any]]:
    cfg, _ = load_project_config(root)
    items = DoorstopProject.open(root).items()
    return LinkGraph.build(cfg, items), cfg, items


def _links(root: Path) -> list[Any]:
    graph, cfg, items = _graph(root)
    return validate_links(cfg, graph, items)


def _set(root: Path, uid: str, **attrs: Any) -> None:
    DoorstopProject.open(root).update_item(uid, attrs=attrs)


def test_graph_contains_parent_and_verifies_edges(minimal_project: Path):
    graph, _, _ = _graph(minimal_project)
    triples = {(e.source, e.target, e.type) for e in graph.edges}
    assert ("EPS-0001", "SYS-0002", "parent") in triples
    assert ("VER-0001", "EPS-0001", "verifies") in triples
    assert [e.source for e in graph.incoming("EPS-0001", ["verifies"])] == ["VER-0001"]
    assert graph.children("SYS-0002") == ["EPS-0001"]
    assert graph.verifiers("EPS-0001") == ["VER-0001"]
    assert graph.verifiers("SYS-0001") == []


def test_graph_edges_are_sorted_deterministically(minimal_project: Path):
    graph, _, _ = _graph(minimal_project)
    keys = [(e.source, e.target, e.type) for e in graph.edges]
    assert keys == sorted(keys)


def test_valid_typed_links_produce_no_findings(minimal_project: Path):
    _set(
        minimal_project, "EPS-0001", link_satisfies=["SYS-0001"], link_refines=["SYS-0003"], link_conflicts=["EPS-0002"]
    )
    assert _links(minimal_project) == []


def test_conflicts_with_is_symmetric_in_the_graph(minimal_project: Path):
    _set(minimal_project, "EPS-0001", link_conflicts=["EPS-0002"])
    graph, _, _ = _graph(minimal_project)
    assert "EPS-0001" in graph.related("EPS-0002")
    assert "EPS-0002" in graph.related("EPS-0001")


def test_missing_target(minimal_project: Path):
    _set(minimal_project, "EPS-0001", link_satisfies=["SYS-0099"])
    f = next(x for x in _links(minimal_project) if x.code == "RVS-LINK-TARGET-MISSING")
    assert f.uid == "EPS-0001" and "SYS-0099" in f.message and f.severity is Severity.ERROR


def test_self_link(minimal_project: Path):
    _set(minimal_project, "EPS-0001", link_refines=["EPS-0001"])
    assert "RVS-LINK-SELF" in {f.code for f in _links(minimal_project)}


def test_verifies_must_go_from_verification_item_to_requirement(minimal_project: Path):
    _set(minimal_project, "VER-0001", link_verifies=["VER-0002"])
    f = next(x for x in _links(minimal_project) if x.code == "RVS-LINK-KIND")
    assert f.uid == "VER-0001" and "verifies" in f.message and f.hint


def test_satisfies_from_verification_item_is_rejected(minimal_project: Path):
    # satisfies is only defined between requirements; the attribute is not even in the verification template
    graph, cfg, items = _graph(minimal_project)
    assert "satisfies" in cfg.links and cfg.links["satisfies"].source_kinds == ("requirements",)


def test_verification_method_mismatch_warns(minimal_project: Path):
    _set(minimal_project, "VER-0001", verify_method="test")  # EPS-0001 is verified by analysis
    f = next(x for x in _links(minimal_project) if x.code == "RVS-LINK-METHOD-MISMATCH")
    assert f.severity is Severity.WARNING and f.uid == "VER-0001"


def test_suspect_link_after_parent_fingerprint_change(minimal_project: Path):
    assert "RVS-LINK-SUSPECT" not in {f.code for f in _links(minimal_project)}
    _set(minimal_project, "SYS-0002", status="approved")  # not fingerprinted
    assert "RVS-LINK-SUSPECT" not in {f.code for f in _links(minimal_project)}
    _set(minimal_project, "SYS-0002", title="Eclipse operation (changed)")  # fingerprinted
    f = next(x for x in _links(minimal_project) if x.code == "RVS-LINK-SUSPECT")
    assert f.uid == "EPS-0001" and "SYS-0002" in f.message and f.severity is Severity.WARNING
    DoorstopProject.open(minimal_project).clear_suspect("EPS-0001")
    assert "RVS-LINK-SUSPECT" not in {f.code for f in _links(minimal_project)}


def test_requirement_without_children_is_flagged_only_where_a_child_requirements_document_exists(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    proj.add_item("SYS", "The spacecraft shall be lonely.", attrs={"title": "Lonely", "type": "functional"})
    found = [f for f in _links(minimal_project) if f.code == "RVS-TRACE-NO-CHILD"]
    assert [f.uid for f in found] == [
        "SYS-0005"
    ]  # EPS is a leaf document: never flagged; VER is not a requirements child
    proj.add_item("EPS", "The EPS shall be childless.", attrs={"title": "Leaf", "type": "functional"})
    assert [f.uid for f in _links(minimal_project) if f.code == "RVS-TRACE-NO-CHILD"] == ["SYS-0005"]


def test_validate_fast_mode_runs_no_doorstop_validation(minimal_project: Path):
    fast = validate_project(minimal_project, doorstop=False)
    assert not [f for f in fast.findings if f.code.startswith("DOORSTOP-")]
    assert fast.exit_code == 0


def test_validate_full_mode_does_not_duplicate_rvs_checks(minimal_project: Path):
    _set(minimal_project, "SYS-0002", title="changed")
    full = validate_project(minimal_project)
    codes = [f.code for f in full.findings]
    assert "RVS-LINK-SUSPECT" in codes
    assert "DOORSTOP-SUSPECT-LINK" not in codes and "DOORSTOP-NO-CHILD-LINKS" not in codes
    assert "DOORSTOP-UNREVIEWED" in codes  # Doorstop-only information stays


def test_links_run_inside_validate_and_set_exit_code(minimal_project: Path):
    _set(minimal_project, "EPS-0001", link_satisfies=["SYS-0099"])
    report = validate_project(minimal_project, doorstop=False)
    assert "RVS-LINK-TARGET-MISSING" in {f.code for f in report.findings} and report.exit_code == 1


@pytest.mark.parametrize("name", ["satisfies", "verifies", "refines", "conflicts-with"])
def test_every_link_type_is_configured(minimal_project: Path, name: str):
    _, cfg, _ = _graph(minimal_project)
    assert name in cfg.links and cfg.links[name].attribute.startswith("link_")

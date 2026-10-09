from pathlib import Path
from typing import Any

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.trace import LinkGraph, coverage, impact, neighbourhood


def _ctx(root: Path) -> tuple[Any, Any, Any]:
    cfg, _ = load_project_config(root)
    items = DoorstopProject.open(root).items()
    return cfg, items, LinkGraph.build(cfg, items)


# impact analysis ---------------------------------------------------------------
def test_impact_lists_everything_downstream_as_tree_and_list(minimal_project: Path):
    _, _, graph = _ctx(minimal_project)
    result = impact(graph, "SYS-0002")
    assert [(n.uid, n.depth, n.via) for n in result.flat()] == [("EPS-0001", 1, "parent"), ("VER-0001", 2, "verifies")]
    (child,) = result.root.children
    assert child.uid == "EPS-0001" and [c.uid for c in child.children] == ["VER-0001"]
    assert result.count == 2


def test_impact_of_a_leaf_is_empty(minimal_project: Path):
    _, _, graph = _ctx(minimal_project)
    assert impact(graph, "VER-0001").count == 0


def test_impact_follows_satisfies_and_refines_and_lists_conflicts_separately(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    proj.update_item("EPS-0002", attrs={"link_satisfies": ["SYS-0002"]})
    proj.update_item("EPS-0003", attrs={"link_conflicts": ["SYS-0002"]})
    _, _, graph = _ctx(minimal_project)
    result = impact(graph, "SYS-0002")
    assert {n.uid for n in result.flat()} == {
        "EPS-0001",
        "EPS-0002",
        "VER-0001",
        "VER-0002",
    }  # EPS-0002 is verified by VER-0002
    assert result.related == ("EPS-0003",)


def test_impact_survives_cycles(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    proj.update_item("EPS-0001", attrs={"link_refines": ["EPS-0002"]})
    proj.update_item("EPS-0002", attrs={"link_refines": ["EPS-0001"]})
    _, _, graph = _ctx(minimal_project)
    assert impact(graph, "EPS-0001").count >= 1


# neighbourhood --------------------------------------------------------------------
def test_neighbourhood_layers(minimal_project: Path):
    _, _, graph = _ctx(minimal_project)
    n = neighbourhood(graph, "EPS-0001", depth=1)
    assert {x.uid: x.layer for x in n.nodes} == {"SYS-0002": -1, "EPS-0001": 0, "VER-0001": 1}
    assert {(e.source, e.target, e.type) for e in n.edges} == {
        ("EPS-0001", "SYS-0002", "parent"),
        ("VER-0001", "EPS-0001", "verifies"),
    }


def test_neighbourhood_depth_two_reaches_further(minimal_project: Path):
    _, _, graph = _ctx(minimal_project)
    n = neighbourhood(graph, "EPS-0001", depth=2)
    assert "SYS-0002" in {x.uid for x in n.nodes}
    assert len(n.nodes) == 3  # SYS-0002 has no other neighbours except EPS-0001


def test_neighbourhood_unknown_item(minimal_project: Path):
    _, _, graph = _ctx(minimal_project)
    assert neighbourhood(graph, "NOPE-1", depth=1).nodes == ()


# coverage ----------------------------------------------------------------------------
def test_coverage_per_document(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    rows = {r.prefix: r for r in coverage(cfg, items, graph)}
    assert set(rows) == {"SYS", "EPS", "VER"}
    assert rows["SYS"].total == 3 and rows["SYS"].by_status == {"draft": 3}
    assert rows["SYS"].by_verification == {"not verified": 3}
    assert rows["EPS"].by_verification == {"planned": 3}
    assert rows["VER"].total == 3 and rows["VER"].by_status == {"planned": 3} and rows["VER"].by_verification == {}


def test_coverage_percentages_and_order(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    rows = coverage(cfg, items, graph)
    assert [r.prefix for r in rows] == ["SYS", "EPS", "VER"]  # project file order
    assert rows[0].share("draft") == 1.0 and rows[0].share("approved") == 0.0

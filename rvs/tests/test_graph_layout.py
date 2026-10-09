from pathlib import Path

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.trace import LinkGraph, neighbourhood
from rvs_gui.graph_layout import layout


def test_layers_map_to_rows_and_nodes_do_not_overlap(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    graph = LinkGraph.build(cfg, DoorstopProject.open(minimal_project).items())
    n = neighbourhood(graph, "SYS-0002", depth=2)
    pos = layout(n)
    assert set(pos) == {x.uid for x in n.nodes}
    ys = {x.uid: pos[x.uid][1] for x in n.nodes}
    assert ys["SYS-0002"] < ys["EPS-0001"] < ys["VER-0001"]  # upstream above, downstream below
    boxes = [(x, y) for x, y in pos.values()]
    assert len(set(boxes)) == len(boxes)


def test_siblings_in_a_layer_are_spread_horizontally(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    DoorstopProject.open(minimal_project).update_item("SYS-0001", attrs={"link_satisfies": []})
    graph = LinkGraph.build(cfg, DoorstopProject.open(minimal_project).items())
    pos = layout(neighbourhood(graph, "EPS-0001", depth=1))
    assert pos["EPS-0001"][1] != pos["SYS-0002"][1]

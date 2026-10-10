"""Layered layout for the link graph: one row per layer (upstream above), nodes centred in their row."""

from rvs_core.trace import Neighbourhood

X_STEP = 220.0
Y_STEP = 130.0


def layout(n: Neighbourhood) -> dict[str, tuple[float, float]]:
    by_layer: dict[int, list[str]] = {}
    for node in n.nodes:
        by_layer.setdefault(node.layer, []).append(node.uid)
    pos: dict[str, tuple[float, float]] = {}
    for layer, uids in by_layer.items():
        uids.sort()
        for i, uid in enumerate(uids):
            pos[uid] = ((i - (len(uids) - 1) / 2) * X_STEP, layer * Y_STEP)
    return pos

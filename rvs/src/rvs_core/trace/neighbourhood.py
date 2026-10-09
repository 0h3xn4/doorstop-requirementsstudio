"""Neighbourhood of one item for the graph view: nodes with a layer relative to the centre, plus edges."""

from collections import deque
from dataclasses import dataclass

from rvs_core.trace.graph import Edge, LinkGraph


@dataclass(frozen=True)
class NeighbourNode:
    uid: str
    layer: int  # negative: upstream (parents, verified requirements); positive: downstream (children, verifiers)
    distance: int


@dataclass(frozen=True)
class Neighbourhood:
    centre: str
    nodes: tuple[NeighbourNode, ...]
    edges: tuple[Edge, ...]


def neighbourhood(graph: LinkGraph, uid: str, depth: int = 1) -> Neighbourhood:
    if uid not in graph.uids:
        return Neighbourhood(uid, (), ())
    layer = {uid: 0}
    dist = {uid: 0}
    queue = deque([uid])
    while queue:
        cur = queue.popleft()
        if dist[cur] >= depth:
            continue
        steps = [(e.target, layer[cur] - (0 if e.type in graph.symmetric else 1)) for e in graph.outgoing(cur)]
        steps += [(e.source, layer[cur] + (0 if e.type in graph.symmetric else 1)) for e in graph.incoming(cur)]
        for other, lay in sorted(steps):
            if other not in layer:
                layer[other], dist[other] = lay, dist[cur] + 1
                queue.append(other)
    members = set(layer)
    edges = tuple(e for e in graph.edges if e.source in members and e.target in members)
    nodes = tuple(sorted((NeighbourNode(u, layer[u], dist[u]) for u in members), key=lambda n: (n.layer, n.uid)))
    return Neighbourhood(uid, nodes, edges)

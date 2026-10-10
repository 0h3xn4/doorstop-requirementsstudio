"""Impact analysis: everything downstream of an item that a change could affect."""

from collections import deque
from dataclasses import dataclass, field

from rvs_core.trace.graph import PARENT, LinkGraph

DOWNSTREAM = (PARENT, "satisfies", "refines", "verifies")  # items that point at the changed item depend on it


@dataclass
class ImpactNode:
    uid: str
    depth: int = 0
    via: str = ""
    children: list["ImpactNode"] = field(default_factory=list)


@dataclass
class ImpactResult:
    root: ImpactNode
    related: tuple[str, ...] = ()  # symmetric links (conflicts-with): not downstream, but worth a look

    def flat(self) -> list[ImpactNode]:
        out: list[ImpactNode] = []
        stack = [iter(self.root.children)]  # pre-order without recursion: a chain of 1,000 links must not overflow
        while stack:
            child = next(stack[-1], None)
            if child is None:
                stack.pop()
                continue
            out.append(child)
            stack.append(iter(child.children))
        return out

    @property
    def count(self) -> int:
        return len(self.flat())


def impact(graph: LinkGraph, uid: str) -> ImpactResult:
    root = ImpactNode(uid)
    seen = {uid}

    queue = deque([root])  # breadth first, so an item reachable by several routes sits at its shallowest depth
    while queue:
        node = queue.popleft()
        for edge in sorted(graph.incoming(node.uid, DOWNSTREAM), key=lambda e: (e.source, e.type)):
            if edge.source in seen:
                continue  # cycles and diamonds: list every affected item once
            seen.add(edge.source)
            child = ImpactNode(edge.source, node.depth + 1, edge.type)
            node.children.append(child)
            queue.append(child)
    return ImpactResult(root, tuple(r for r in graph.related(uid) if r not in seen))

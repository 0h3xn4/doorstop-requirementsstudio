"""Impact analysis: everything downstream of an item that a change could affect."""

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

        def walk(node: ImpactNode) -> None:
            for child in node.children:
                out.append(child)
                walk(child)

        walk(self.root)
        return out

    @property
    def count(self) -> int:
        return len(self.flat())


def impact(graph: LinkGraph, uid: str) -> ImpactResult:
    root = ImpactNode(uid)
    seen = {uid}

    def expand(node: ImpactNode) -> None:
        for edge in sorted(graph.incoming(node.uid, DOWNSTREAM), key=lambda e: (e.source, e.type)):
            if edge.source in seen:
                continue  # cycles and diamonds: list every affected item once, at its shallowest depth
            seen.add(edge.source)
            child = ImpactNode(edge.source, node.depth + 1, edge.type)
            node.children.append(child)
        for child in node.children:
            expand(child)

    expand(root)
    return ImpactResult(root, tuple(r for r in graph.related(uid) if r not in seen))

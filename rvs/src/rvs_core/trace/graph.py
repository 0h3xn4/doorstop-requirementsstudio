"""The link graph: Doorstop parent links plus RVS typed links, built from item snapshots."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig

PARENT = "parent"


@dataclass(frozen=True, order=True)
class Edge:
    """``source`` points to ``target`` (a child to its parent, a verification item to the requirement it verifies)."""

    source: str
    target: str
    type: str


@dataclass(frozen=True)
class Unresolved:
    source: str
    target: str
    type: str


class LinkGraph:
    def __init__(
        self,
        edges: Iterable[Edge],
        unresolved: Iterable[Unresolved],
        symmetric: frozenset[str],
        uids: frozenset[str],
    ) -> None:
        self.edges: tuple[Edge, ...] = tuple(sorted(set(edges)))
        self.unresolved: tuple[Unresolved, ...] = tuple(
            sorted(set(unresolved), key=lambda u: (u.source, u.target, u.type))
        )
        self.symmetric = symmetric
        self.uids = uids
        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}
        for e in self.edges:
            self._out.setdefault(e.source, []).append(e)
            self._in.setdefault(e.target, []).append(e)

    @classmethod
    def build(cls, cfg: ProjectConfig, items: Sequence[ItemData]) -> "LinkGraph":
        uids = frozenset(i.uid for i in items)
        edges: list[Edge] = []
        unresolved: list[Unresolved] = []

        def add(source: str, target: str, kind: str) -> None:
            if target in uids:
                edges.append(Edge(source, target, kind))
            else:
                unresolved.append(Unresolved(source, target, kind))

        for item in items:
            for parent in item.links:
                add(item.uid, parent, PARENT)
            for name, definition in cfg.links.items():
                targets = item.attrs.get(definition.attribute)
                for target in targets if isinstance(targets, list) else []:  # wrong types: RVS-ATTR-TYPE
                    add(item.uid, str(target), name)
        sym = frozenset(n for n, d in cfg.links.items() if d.symmetric)
        return cls(edges, unresolved, sym, uids)

    # queries ####################################################################
    def outgoing(self, uid: str, types: Iterable[str] | None = None) -> list[Edge]:
        wanted = set(types) if types is not None else None
        return [e for e in self._out.get(uid, []) if wanted is None or e.type in wanted]

    def incoming(self, uid: str, types: Iterable[str] | None = None) -> list[Edge]:
        wanted = set(types) if types is not None else None
        return [e for e in self._in.get(uid, []) if wanted is None or e.type in wanted]

    def children(self, uid: str) -> list[str]:
        return sorted(e.source for e in self.incoming(uid, [PARENT]))

    def verifiers(self, uid: str) -> list[str]:
        return sorted({e.source for e in self.incoming(uid, ["verifies"])})

    def related(self, uid: str) -> list[str]:
        """Items linked to ``uid`` by a symmetric link type (conflicts-with), in either direction."""
        out = {e.target for e in self._out.get(uid, []) if e.type in self.symmetric}
        inc = {e.source for e in self._in.get(uid, []) if e.type in self.symmetric}
        return sorted(out | inc)


def doc_of(uid: str) -> str:
    return uid.rsplit("-", 1)[0]


def by_uid(items: Iterable[ItemData]) -> Mapping[str, ItemData]:
    return {i.uid: i for i in items}

"""Traceability matrix between two documents, either direction, with gaps flagged."""

from collections.abc import Sequence

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.matrices.provenance import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_core.trace.graph import LinkGraph


def _doc_order(cfg: ProjectConfig) -> dict[str, int]:
    return {d.prefix: n for n, d in enumerate(cfg.project.documents)}


def build_traceability(
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    graph: LinkGraph,
    source: str,
    target: str,
    direction: str,
    *,
    provenance: Provenance,
) -> MatrixTable:
    """Rows are the items of ``source``.

    ``direction='down'``: linked items are items of ``target`` that point at the row's item (its children,
    verifiers, satisfiers). ``direction='up'``: linked items are items of ``target`` the row's item points at.
    Gaps: childless / unverified(-approved) for 'down', orphan for 'up'; derived items are never orphans.
    """
    src_decl, dst_decl = cfg.project.document(source), cfg.project.document(target)
    for prefix, decl in ((source, src_decl), (target, dst_decl)):
        if decl is None:
            raise ValueError(f"Document {prefix} does not exist in this project.")
    assert src_decl is not None and dst_decl is not None
    if direction not in ("down", "up"):
        raise ValueError("direction must be 'down' or 'up'")
    by = {i.uid: i for i in items}
    approved = set()
    for rule in cfg.rules["rules"]:
        if rule["id"] == "verified-when-approved":
            approved = set(rule.get("params", {}).get("statuses", ["approved"]))
    cols = list(
        cfg.exports.get("traceability", {}).get("columns") or ["Source", "Title", "Linked items", "Link types", "Gap"]
    )
    rows: list[list[str]] = []
    flags: list[str | None] = []
    sources = [i for i in items if i.document == source and i.normative and i.active]
    sources.sort(key=lambda i: (i.level_key, i.uid))
    for item in sources:
        edges = (
            [e for e in graph.incoming(item.uid) if e.type not in graph.symmetric and by[e.source].document == target]
            if direction == "down"
            else [
                e for e in graph.outgoing(item.uid) if e.type not in graph.symmetric and by[e.target].document == target
            ]
        )
        linked = sorted({e.source if direction == "down" else e.target for e in edges})
        types = sorted({e.type for e in edges})
        flag: str | None = None
        if not linked:
            if direction == "up":
                flag = None if item.derived or src_decl.parent is None else "orphan"
            elif dst_decl.kind == "verification":
                flag = "unverified-approved" if item.attrs.get("status") in approved else "unverified"
            else:
                flag = "childless"
        title = str(item.attrs.get("title") or item.header or "")
        rows.append([item.uid, title, ", ".join(linked), ", ".join(types), flag or ""])
        flags.append(flag)
    arrow = "→" if direction == "down" else "←"
    return MatrixTable(f"Traceability {source} {arrow} {target}", cols, rows, flags, provenance)

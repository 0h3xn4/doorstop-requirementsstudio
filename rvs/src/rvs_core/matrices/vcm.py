"""Verification control matrix: every requirement with method, level, verifying items, status and evidence."""

from collections.abc import Sequence
from dataclasses import dataclass

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.matrices.provenance import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_core.trace.graph import LinkGraph
from rvs_core.trace.status import NOT_VERIFIED, aggregate_status


@dataclass(frozen=True)
class VcmFilter:
    documents: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()  # aggregated verification status
    only_gaps: bool = False  # requirements that nothing verifies


def build_vcm(
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    graph: LinkGraph,
    flt: VcmFilter | None = None,
    *,
    provenance: Provenance,
) -> MatrixTable:
    flt = flt or VcmFilter()
    by = {i.uid: i for i in items}
    order = {d.prefix: n for n, d in enumerate(cfg.project.documents)}
    kinds = {d.prefix: d.kind for d in cfg.project.documents}
    spec = cfg.exports["vcm"]["columns"]
    keys = [c["key"] for c in spec]
    reqs = [i for i in items if kinds.get(i.document) == "requirements" and i.normative and i.active]
    reqs.sort(key=lambda i: (order.get(i.document, 999), i.level_key, i.uid))
    rows: list[list[str]] = []
    for req in reqs:
        ver = [by[v] for v in graph.verifiers(req.uid)]
        agg = aggregate_status(str(v.attrs.get("v_status") or "") for v in ver)
        if flt.documents and req.document not in flt.documents:
            continue
        if flt.methods and req.attrs.get("verify_method") not in flt.methods:
            continue
        if flt.levels and req.attrs.get("verify_level") not in flt.levels:
            continue
        if flt.statuses and agg not in flt.statuses:
            continue
        if flt.only_gaps and agg != NOT_VERIFIED:
            continue
        values = {
            "uid": req.uid,
            "title": str(req.attrs.get("title") or ""),
            "document": req.document,
            "status": str(req.attrs.get("status") or ""),
            "priority": str(req.attrs.get("priority") or ""),
            "verify_method": str(req.attrs.get("verify_method") or ""),
            "verify_level": str(req.attrs.get("verify_level") or ""),
            "verification_item": ", ".join(v.uid for v in ver),
            "v_status": agg,
            "evidence": "; ".join(str(v.attrs["evidence"]) for v in ver if v.attrs.get("evidence")),
        }
        unknown = [k for k in keys if k not in values]
        if unknown:
            raise ValueError(f"config/exports.yaml: unknown VCM column key(s) {', '.join(unknown)}.")
        rows.append([values[k] for k in keys])
    notes: tuple[str, ...] = ()
    if cfg.exports["vcm"].get("layout_source") == "TODO-STANDARD":
        notes = ("Column layout is a placeholder (TODO-STANDARD): it does not yet follow ECSS-E-ST-10-02C.",)
    return MatrixTable(
        "Verification control matrix", [c["title"] for c in spec], rows, [None] * len(rows), provenance, notes
    )

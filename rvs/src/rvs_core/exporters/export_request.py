"""A request for one output ("the VCM as PDF"), shared by the CLI and the GUI."""

from collections.abc import Sequence
from dataclasses import dataclass

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.exporters import DOC_FORMATS, render_doc, render_table
from rvs_core.exporters.builders import spec_doc
from rvs_core.exporters.itemsio import export_items_csv, export_items_xlsx
from rvs_core.exporters.reqif import export_reqif
from rvs_core.matrices import Provenance, VcmFilter, build_traceability, build_vcm, coverage_table, impact_table
from rvs_core.trace import LinkGraph, coverage, impact

KINDS = ("vcm", "trace", "coverage", "impact", "items", "spec", "reqif")


@dataclass(frozen=True)
class ExportRequest:
    kind: str  # one of KINDS
    fmt: str
    documents: tuple[str, ...] = ()  # vcm filter, or the documents of a spec (empty = all)
    methods: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    only_gaps: bool = False
    trace: tuple[str, str, str] = ("", "", "down")  # source, target, direction
    impact_uid: str = ""

    def formats(self) -> tuple[str, ...]:
        return available_formats(self.kind)


def available_formats(kind: str) -> tuple[str, ...]:
    if kind == "reqif":
        return ("reqif",)
    if kind == "items":
        return ("csv", "xlsx")
    if kind == "spec":
        return DOC_FORMATS
    return ("csv", "json", "xlsx", "html", "docx", "pdf")


def build_output(
    request: ExportRequest, cfg: ProjectConfig, items: Sequence[ItemData], graph: LinkGraph, prov: Provenance
) -> bytes:
    """Render the request. Raises ValueError with a plain-language message for an invalid request."""
    if request.kind not in KINDS:
        raise ValueError(f"Unknown export '{request.kind}'.")
    if request.fmt not in available_formats(request.kind):
        raise ValueError(
            f"{request.kind} can be written as {', '.join(available_formats(request.kind))}, not {request.fmt}."
        )
    if request.kind == "reqif":
        return export_reqif(cfg, items, prov, request.documents)
    if request.kind == "items":
        return export_items_csv(cfg, items, prov) if request.fmt == "csv" else export_items_xlsx(cfg, items, prov)
    if request.kind == "spec":
        return render_doc(spec_doc(cfg, items, graph, request.documents or None, prov), request.fmt)
    if request.kind == "vcm":
        flt = VcmFilter(request.documents, request.methods, request.levels, request.statuses, request.only_gaps)
        table = build_vcm(cfg, items, graph, flt, provenance=prov)
    elif request.kind == "trace":
        source, target, direction = request.trace
        table = build_traceability(cfg, items, graph, source, target, direction, provenance=prov)
    elif request.kind == "coverage":
        table = coverage_table(cfg, coverage(cfg, items, graph), prov)
    else:
        if request.impact_uid not in graph.uids:
            raise ValueError(f"Item {request.impact_uid} does not exist in this project.")
        table = impact_table(items, impact(graph, request.impact_uid), prov)
    return render_table(table, request.fmt)

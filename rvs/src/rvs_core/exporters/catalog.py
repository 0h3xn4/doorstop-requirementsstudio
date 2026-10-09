"""Every output the tool can produce for one project, keyed by file name (used by golden tests)."""

from collections.abc import Sequence

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.exporters import DOC_FORMATS, TABLE_FORMATS, render_doc, render_table
from rvs_core.exporters.builders import spec_doc
from rvs_core.exporters.itemsio import export_items_csv, export_items_xlsx
from rvs_core.matrices import Provenance, VcmFilter, build_traceability, build_vcm, coverage_table, impact_table
from rvs_core.trace import LinkGraph, coverage, impact


def all_outputs(
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    graph: LinkGraph,
    prov: Provenance,
    *,
    trace: tuple[str, str, str],
    impact_uid: str,
) -> dict[str, bytes]:
    tables = {
        "vcm": build_vcm(cfg, items, graph, VcmFilter(), provenance=prov),
        f"trace-{trace[0]}-{trace[1]}-{trace[2]}": build_traceability(cfg, items, graph, *trace, provenance=prov),
        "coverage": coverage_table(cfg, coverage(cfg, items, graph), prov),
        f"impact-{impact_uid}": impact_table(items, impact(graph, impact_uid), prov),
    }
    out: dict[str, bytes] = {}
    for name, table in tables.items():
        for fmt in TABLE_FORMATS:
            out[f"{name}.{fmt}"] = render_table(table, fmt)
    out["items.csv"] = export_items_csv(cfg, items, prov)
    out["items.xlsx"] = export_items_xlsx(cfg, items, prov)
    spec = spec_doc(cfg, items, graph, None, prov)
    for fmt in DOC_FORMATS:
        out[f"spec.{fmt}"] = render_doc(spec, fmt)
    return dict(sorted(out.items()))

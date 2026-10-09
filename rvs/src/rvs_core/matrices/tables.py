"""Other result sets rendered as MatrixTable: coverage and impact analysis."""

from collections.abc import Sequence

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.matrices.provenance import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_core.trace.coverage import CoverageRow
from rvs_core.trace.impact import ImpactResult
from rvs_core.trace.status import ORDER


def coverage_table(cfg: ProjectConfig, rows: Sequence[CoverageRow], provenance: Provenance) -> MatrixTable:
    statuses = list(cfg.vocab.values("status"))
    vstatuses = list(cfg.vocab.values("verification_status"))
    ver_states = [s for s in ORDER if s in vstatuses or s == "not verified"]
    cols = ["Document", "Title", "Items"]
    cols += [f"{s} (n)" for s in statuses] + [f"{s} (%)" for s in statuses]
    cols += [f"verif: {s} (n)" for s in ver_states] + [f"verif: {s} (%)" for s in ver_states]
    out: list[list[str]] = []
    for r in rows:
        if r.kind == "requirements":
            counts = [r.by_status.get(s, 0) for s in statuses]
            vcounts = [r.by_verification.get(s, 0) for s in ver_states]
        else:  # verification items: their own status vocabulary is shown under the verification columns
            counts = [0 for _ in statuses]
            vcounts = [r.by_status.get(s, 0) for s in ver_states]
        total = r.total
        pct = [f"{(100 * n / total) if total else 0:.0f}" for n in counts]
        vpct = [f"{(100 * n / total) if total else 0:.0f}" for n in vcounts]
        out.append([r.prefix, r.title, str(total), *map(str, counts), *pct, *map(str, vcounts), *vpct])
    return MatrixTable("Coverage by document", cols, out, [None] * len(out), provenance)


def impact_table(items: Sequence[ItemData], result: ImpactResult, provenance: Provenance) -> MatrixTable:
    by = {i.uid: i for i in items}
    rows = [
        [n.uid, str(n.depth), n.via, str(by[n.uid].attrs.get("title") or by[n.uid].header or "")] for n in result.flat()
    ]
    notes = (f"Related by conflicts-with (not downstream): {', '.join(result.related)}",) if result.related else ()
    return MatrixTable(
        f"Impact of changing {result.root.uid}",
        ["Item", "Depth", "Via", "Title"],
        rows,
        [None] * len(rows),
        provenance,
        notes,
    )

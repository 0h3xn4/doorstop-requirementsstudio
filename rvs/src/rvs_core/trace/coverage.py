"""Coverage dashboard data: per document, items per status and per verification state."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.trace.graph import LinkGraph
from rvs_core.trace.status import ORDER, aggregate_status


@dataclass(frozen=True)
class CoverageRow:
    prefix: str
    title: str
    kind: str
    total: int
    by_status: dict[str, int] = field(default_factory=dict)  # requirement status, or v_status for verification items
    by_verification: dict[str, int] = field(default_factory=dict)  # requirements only

    def share(self, key: str, *, verification: bool = False) -> float:
        counts = self.by_verification if verification else self.by_status
        return counts.get(key, 0) / self.total if self.total else 0.0


def _ordered(counts: dict[str, int], order: Sequence[str]) -> dict[str, int]:
    known = [k for k in order if counts.get(k)]
    return {k: counts[k] for k in [*known, *sorted(k for k in counts if k not in order)]}


def coverage(cfg: ProjectConfig, items: Sequence[ItemData], graph: LinkGraph) -> list[CoverageRow]:
    by_uid = {i.uid: i for i in items}
    rows: list[CoverageRow] = []
    for decl in cfg.project.documents:
        docs = [i for i in items if i.document == decl.prefix and i.normative and i.active]
        status_key = "status" if decl.kind == "requirements" else "v_status"
        order = cfg.vocab.values("status" if decl.kind == "requirements" else "verification_status")
        statuses: dict[str, int] = {}
        verification: dict[str, int] = {}
        for item in docs:
            st = str(item.attrs.get(status_key) or "")
            statuses[st or "(unset)"] = statuses.get(st or "(unset)", 0) + 1
            if decl.kind == "requirements":
                agg = aggregate_status(str(by_uid[v].attrs.get("v_status") or "") for v in graph.verifiers(item.uid))
                verification[agg] = verification.get(agg, 0) + 1
        rows.append(
            CoverageRow(
                decl.prefix, decl.title, decl.kind, len(docs), _ordered(statuses, order), _ordered(verification, ORDER)
            )
        )
    return rows

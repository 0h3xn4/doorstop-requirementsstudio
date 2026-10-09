"""Builders: turn matrices and project documents into the neutral Doc model."""

from collections.abc import Sequence

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.exporters.model import Doc, Entry, Heading, Paragraph, TableBlock
from rvs_core.matrices.provenance import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_core.trace import LinkGraph

_LANDSCAPE_FROM = 5  # columns


def matrix_doc(table: MatrixTable) -> Doc:
    block = TableBlock(tuple(table.columns), tuple(tuple(r) for r in table.rows), tuple(table.flags))
    return Doc(table.title, table.provenance, (block,), table.notes, landscape=len(table.columns) > _LANDSCAPE_FROM)


_FIELD_ORDER = ("type", "status", "priority", "owner", "source", "standard_clause", "verify_method", "verify_level",
                "proc_id", "v_status", "evidence", "responsible", "executed_on")  # fmt: skip
_LINK_LABEL = {"link_satisfies": "Satisfies", "link_refines": "Refines", "link_conflicts": "Conflicts with",
               "link_verifies": "Verifies"}  # fmt: skip


def _pretty(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _entry(item: ItemData, graph: LinkGraph) -> Entry:
    fields: list[tuple[str, str]] = []
    for name in _FIELD_ORDER:
        value = item.attrs.get(name)
        if value not in (None, "", []):
            fields.append((_pretty(name), str(value)))
    if item.links:
        fields.append(("Parents", ", ".join(item.links)))
    for attr, label in _LINK_LABEL.items():
        value = item.attrs.get(attr)
        if value:
            fields.append((label, ", ".join(str(v) for v in value)))
    verifiers = graph.verifiers(item.uid)
    if verifiers:
        fields.append(("Verified by", ", ".join(verifiers)))
    return Entry(
        item.uid,
        str(item.attrs.get("title") or ""),
        item.text.strip(),
        tuple(fields),
        str(item.attrs.get("rationale") or ""),
    )


def spec_doc(
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    graph: LinkGraph,
    prefixes: Sequence[str] | None,
    provenance: Provenance,
    title: str | None = None,
) -> Doc:
    """A specification document: per document a heading, then its items in level order."""
    order = [d.prefix for d in cfg.project.documents]
    wanted = list(prefixes) if prefixes else order
    for prefix in wanted:
        if cfg.project.document(prefix) is None:
            raise ValueError(f"Document {prefix} does not exist in this project.")
    blocks: list[Heading | Paragraph | Entry] = []
    for prefix in sorted(wanted, key=order.index):
        decl = cfg.project.document(prefix)
        assert decl is not None
        blocks.append(Heading(1, f"{prefix} — {decl.title}"))
        for item in sorted((i for i in items if i.document == prefix and i.active), key=lambda i: (i.level_key, i.uid)):
            if not item.normative:
                if item.header:
                    blocks.append(Heading(2, item.header))
                if item.text.strip():
                    blocks.append(Paragraph(item.text.strip()))
                continue
            blocks.append(_entry(item, graph))
    name = title or (f"{wanted[0]} specification" if len(wanted) == 1 else f"{provenance.project} specification")
    return Doc(name, provenance, tuple(blocks))

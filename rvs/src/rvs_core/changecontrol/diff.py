"""Snapshots (a baseline or the working copy) and the differences between two of them."""

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rvs_core.adapter import DoorstopProject, ItemData
from rvs_core.changecontrol.baselines import snapshot_dir
from rvs_core.config import ProjectConfig, load_project_config
from rvs_core.exporters.itemsio import encode
from rvs_core.exporters.model import Block, DiffEntry, DiffField, Doc, Heading, Paragraph
from rvs_core.matrices.provenance import Provenance
from rvs_core.matrices.table import MatrixTable

WORKING = "working copy"
Segment = tuple[str, str]  # (op, text) with op in "equal", "insert", "delete"


@dataclass(frozen=True)
class Snapshot:
    label: str
    cfg: ProjectConfig
    items: dict[str, ItemData]


def load_snapshot(root: Path, ref: str | None) -> Snapshot:
    """``ref`` is a baseline name, or None for the working copy."""
    if ref is None:
        folder, label = Path(root), WORKING
    else:
        folder, label = snapshot_dir(Path(root), ref), ref
    cfg, _ = load_project_config(folder)
    return Snapshot(label, cfg, {i.uid: i for i in DoorstopProject.open(folder).items()})


def text_segments(before: str, after: str) -> list[Segment]:
    """Word-level differences, whitespace kept, adjacent segments of one kind merged."""
    a, b = re.findall(r"\s+|\S+", before), re.findall(r"\s+|\S+", after)
    out: list[Segment] = []

    def add(op: str, tokens: Sequence[str]) -> None:
        text = "".join(tokens)
        if text:
            if out and out[-1][0] == op:
                out[-1] = (op, out[-1][1] + text)
            else:
                out.append((op, text))

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            add("equal", a[i1:i2])
        else:
            if tag in ("delete", "replace"):
                add("delete", a[i1:i2])
            if tag in ("insert", "replace"):
                add("insert", b[j1:j2])
    return out


@dataclass(frozen=True)
class FieldChange:
    name: str
    before: str
    after: str
    segments: tuple[Segment, ...]


@dataclass(frozen=True)
class ItemChange:
    uid: str
    kind: str  # added | removed | changed
    document: str
    title: str
    before: ItemData | None
    after: ItemData | None
    fields: tuple[FieldChange, ...] = ()


@dataclass(frozen=True)
class DiffResult:
    left: str
    right: str
    changes: tuple[ItemChange, ...]

    def _count(self, kind: str) -> int:
        return sum(1 for c in self.changes if c.kind == kind)

    @property
    def added(self) -> int:
        return self._count("added")

    @property
    def removed(self) -> int:
        return self._count("removed")

    @property
    def changed(self) -> int:
        return self._count("changed")

    def for_document(self, prefix: str) -> tuple[ItemChange, ...]:
        return tuple(c for c in self.changes if c.document == prefix)

    def for_item(self, uid: str) -> ItemChange | None:
        return next((c for c in self.changes if c.uid == uid), None)


_HIDDEN = {"rvs_schema_version"}


def _fields(item: ItemData) -> dict[str, str]:
    out = {
        "text": item.text.strip(), "header": item.header, "level": item.level, "normative": encode(item.normative),
        "derived": encode(item.derived), "active": encode(item.active), "ref": item.ref,
        "parents": ", ".join(sorted(item.links)),
    }  # fmt: skip
    for name, value in item.attrs.items():
        if name not in _HIDDEN:
            out[name] = encode(value) if not isinstance(value, list) else ", ".join(str(v) for v in value)
    return out


def _title(item: ItemData | None) -> str:
    return str(item.attrs.get("title") or item.header or "") if item else ""


def diff_snapshots(a: Snapshot, b: Snapshot) -> DiffResult:
    order: dict[str, int] = {}
    for snap in (b, a):
        for d in snap.cfg.project.documents:
            order.setdefault(d.prefix, len(order))
    changes: list[ItemChange] = []
    for uid in sorted(set(a.items) | set(b.items)):
        left, right = a.items.get(uid), b.items.get(uid)
        doc = (right or left).document  # type: ignore[union-attr]
        if left is None:
            changes.append(ItemChange(uid, "added", doc, _title(right), None, right))
        elif right is None:
            changes.append(ItemChange(uid, "removed", doc, _title(left), left, None))
        else:
            fl, fr = _fields(left), _fields(right)
            fields = tuple(
                FieldChange(
                    name, fl.get(name, ""), fr.get(name, ""), tuple(text_segments(fl.get(name, ""), fr.get(name, "")))
                )
                for name in sorted(set(fl) | set(fr), key=lambda n: (n != "text", n))
                if fl.get(name, "") != fr.get(name, "")
            )
            if fields:
                changes.append(ItemChange(uid, "changed", doc, _title(right), left, right, fields))
    changes.sort(key=lambda c: (order.get(c.document, 999), (c.after or c.before).level_key, c.uid))  # type: ignore[union-attr]
    return DiffResult(a.label, b.label, tuple(changes))


# rendering ##########################################################################################
def diff_table(diff: DiffResult, prov: Provenance) -> MatrixTable:
    rows = [[c.uid, c.kind, c.title, ", ".join(f.name for f in c.fields)] for c in diff.changes]
    return MatrixTable(
        f"Changes: {diff.left} → {diff.right}", ["Item", "Change", "Title", "Fields"], rows, [None] * len(rows), prov
    )


def diff_doc(diff: DiffResult, prov: Provenance) -> Doc:
    blocks: list[Block] = [
        Paragraph(f"Added: {diff.added} · Removed: {diff.removed} · Changed: {diff.changed}"),
    ]
    current = ""
    for c in diff.changes:
        if c.document != current:
            current = c.document
            blocks.append(Heading(1, current))
        if c.kind == "changed":
            fields = tuple(DiffField(f.name, f.segments) for f in c.fields)
        else:
            item = c.after or c.before
            assert item is not None
            op = "insert" if c.kind == "added" else "delete"
            fields = (DiffField("text", ((op, item.text.strip()),)),) if item.text.strip() else ()
        blocks.append(DiffEntry(c.uid, c.title, c.kind, fields))
    return Doc(f"Changes: {diff.left} → {diff.right}", prov, tuple(blocks))

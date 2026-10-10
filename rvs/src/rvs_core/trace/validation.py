"""Link validation: targets, direction/kind, consistency, suspect links and missing child items."""

from collections.abc import Sequence

from rvs_core.adapter import ItemData
from rvs_core.config import ProjectConfig
from rvs_core.findings import Finding, Severity
from rvs_core.trace.graph import PARENT, LinkGraph


def _noun(kind: str) -> str:
    return {"requirements": "requirement"}.get(kind, kind) if kind else "unknown kind of item"


def _kind(cfg: ProjectConfig, prefix: str) -> str:
    decl = cfg.project.document(prefix)
    return decl.kind if decl else ""


def validate_links(cfg: ProjectConfig, graph: LinkGraph, items: Sequence[ItemData]) -> list[Finding]:
    by = {i.uid: i for i in items}
    out: list[Finding] = []

    for u in graph.unresolved:
        src = by[u.source]
        what = "parent link" if u.type == PARENT else f"'{u.type}' link"
        out.append(
            Finding(
                "RVS-LINK-TARGET-MISSING", Severity.ERROR,
                f"{u.source} has a {what} to {u.target}, which does not exist.",
                f"Correct the ID or remove the link from {u.source}.", src.path, u.source,
            )
        )  # fmt: skip

    for e in graph.edges:
        src, dst = by[e.source], by[e.target]
        if e.source == e.target:
            out.append(Finding("RVS-LINK-SELF", Severity.ERROR, f"{e.source} has a '{e.type}' link to itself.",
                               "Remove the link.", src.path, e.source))  # fmt: skip
            continue
        if e.type == PARENT:
            continue
        definition = cfg.links[e.type]
        sk, tk = _kind(cfg, src.document), _kind(cfg, dst.document)
        if sk not in definition.source_kinds or tk not in definition.target_kinds:
            out.append(
                Finding(
                    "RVS-LINK-KIND", Severity.ERROR,
                    f"{e.source} ({_noun(sk)}) has a '{e.type}' link to {e.target} ({_noun(tk)}), "
                    f"but '{e.type}' links must go from {' or '.join(map(_noun, definition.source_kinds))} items to "
                    f"{' or '.join(map(_noun, definition.target_kinds))} items.",
                    f"Remove the link from {e.source} or point it at a suitable item.", src.path, e.source,
                )
            )  # fmt: skip
        elif e.type == "verifies":
            ms, mt = src.attrs.get("verify_method"), dst.attrs.get("verify_method")
            if ms and mt and ms != mt:
                out.append(
                    Finding(
                        "RVS-LINK-METHOD-MISMATCH", Severity.WARNING,
                        f"{e.source} verifies {e.target} by {ms}, but {e.target} specifies {mt}.",
                        "Align the verification method on one of the two items.", src.path, e.source,
                    )
                )  # fmt: skip

    for item in items:
        for parent, stamp in item.link_stamps.items():
            target = by.get(parent)
            if target is not None and parent != item.uid and stamp != target.stamp:
                out.append(
                    Finding(
                        "RVS-LINK-SUSPECT", Severity.WARNING,
                        f"{item.uid} links to {parent}, which has changed since the link was last reviewed.",
                        f"Review the change to {parent}, then clear the suspect link on {item.uid}.",
                        item.path, item.uid,
                    )
                )  # fmt: skip

    out.extend(_missing_children(cfg, graph, items))
    return out


def _missing_children(cfg: ProjectConfig, graph: LinkGraph, items: Sequence[ItemData]) -> list[Finding]:
    child_docs: dict[str, set[str]] = {}
    for d in cfg.project.documents:
        if d.parent and d.kind == "requirements":
            child_docs.setdefault(d.parent, set()).add(d.prefix)
    by = {i.uid: i for i in items}
    findings: list[Finding] = []
    for item in items:
        targets = child_docs.get(item.document)
        decl = cfg.project.document(item.document)
        if not targets or decl is None or decl.kind != "requirements" or not (item.normative and item.active):
            continue
        has_child = any(
            by[e.source].document in targets for e in graph.incoming(item.uid, [PARENT, "satisfies", "refines"])
        )
        if not has_child:
            docs = ", ".join(sorted(targets))
            findings.append(
                Finding(
                    "RVS-TRACE-NO-CHILD", Severity.WARNING,
                    f"{item.uid} has no child requirement in {docs}.",
                    "Allocate it to a subsystem requirement, or ignore this if it needs no allocation.",
                    item.path, item.uid,
                )
            )  # fmt: skip
    return findings

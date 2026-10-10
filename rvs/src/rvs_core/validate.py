"""``rvs validate``: schema versions, configuration, RVS attribute rules, and Doorstop's own tree validation."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from rvs_core.adapter import DocumentInfo, DoorstopProject, ItemData, ProjectError, UnreadableItemError
from rvs_core.attrtypes import TYPE_HINT as _TYPE_HINT
from rvs_core.attrtypes import type_ok as _type_ok
from rvs_core.changecontrol.baselines import BaselineError, orphan_tags, verify_baseline
from rvs_core.changecontrol.changes import ChangeRequestError, ChangeRequestStore, validate_change_requests
from rvs_core.changecontrol.manifests import manifest_names, read_manifest
from rvs_core.config import ConfigError, ProjectConfig, load_project_config
from rvs_core.findings import Finding, Severity, sort_findings
from rvs_core.rules import build_context, run_rules
from rvs_core.schema.versioning import VERSION_KEY, SchemaVersionError, migrate
from rvs_core.trace import LinkGraph, validate_links
from rvs_core.vcs.git import GitError

FATAL_CODES = frozenset(
    {
        "RVS-PROJECT-MISSING",
        "RVS-SCHEMA-NEWER",
        "RVS-SCHEMA-MISSING-FATAL",
        "RVS-SCHEMA-INVALID",
        "RVS-SCHEMA-NOMIGRATION",
        "RVS-CONFIG-INVALID",
        "RVS-CONFIG-YAML",
        "RVS-TREE-INVALID",
        "RVS-ITEM-UNREADABLE",
        "RVS-VALIDATION-FAILED",
    }
)
_UID = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+\Z")


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)
    exit_code: int = 0
    config: ProjectConfig | None = None
    items: list[ItemData] = field(default_factory=list)
    docs: list[DocumentInfo] = field(default_factory=list)
    graph: LinkGraph | None = None

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)


def _fatal(code: str, message: str, hint: str, location: str = "") -> ValidationReport:
    return ValidationReport([Finding(code, Severity.ERROR, message, hint, location)], 3)


def _doc_check(cfg: ProjectConfig):  # type: ignore[no-untyped-def]
    def check(doc: DocumentInfo) -> list[Finding]:
        loc = f"{doc.path}/.doorstop.yml"
        decl = cfg.project.document(doc.prefix)
        if decl is None:
            return [
                Finding(
                    "RVS-DOC-UNDECLARED",
                    Severity.ERROR,
                    f"Document {doc.prefix} exists on disk but is not declared in rvs-project.yaml.",
                    f"Add a '{doc.prefix}' entry under 'documents' in rvs-project.yaml, or remove the folder {doc.path}.",
                    loc,
                )
            ]
        out: list[Finding] = []
        if decl.parent != doc.parent:
            out.append(
                Finding(
                    "RVS-DOC-PARENT",
                    Severity.ERROR,
                    f"Document {doc.prefix} has parent {doc.parent or 'none'} in Doorstop but {decl.parent or 'none'} in rvs-project.yaml.",
                    "Make both agree: edit 'parent' in rvs-project.yaml or in the document's .doorstop.yml.",
                    loc,
                )
            )
        if (doc.sep, doc.digits) != (cfg.numbering.sep_for(doc.prefix), cfg.numbering.digits_for(doc.prefix)):
            out.append(
                Finding(
                    "RVS-DOC-NUMBERING",
                    Severity.ERROR,
                    f"Document {doc.prefix} numbers items with separator '{doc.sep}' and {doc.digits} digits, but config/numbering.yaml requires '{cfg.numbering.sep_for(doc.prefix)}' and {cfg.numbering.digits_for(doc.prefix)} digits.",
                    "Change config/numbering.yaml or the document's .doorstop.yml so they match (renumbering existing items is not automatic).",
                    loc,
                )
            )
        expected = cfg.templates.kinds[decl.kind].fingerprint
        if doc.fingerprint != expected:
            out.append(
                Finding(
                    "RVS-DOC-FINGERPRINT",
                    Severity.ERROR,
                    f"Document {doc.prefix} fingerprints {list(doc.fingerprint)} but the '{decl.kind}' template requires {list(expected)}, so suspect-link detection would behave differently.",
                    f"Set 'attributes: reviewed:' in {loc} to the template's fingerprint list.",
                    loc,
                )
            )
        if doc.itemformat != "yaml":
            out.append(
                Finding(
                    "RVS-DOC-FORMAT",
                    Severity.WARNING,
                    f"Document {doc.prefix} uses item format '{doc.itemformat}'; this project standardises on YAML items.",
                    "Keep 'itemformat: yaml' in the document's .doorstop.yml.",
                    loc,
                )
            )
        return out

    return check


def _item_check(cfg: ProjectConfig):  # type: ignore[no-untyped-def]
    def check(item: ItemData, doc: DocumentInfo) -> list[Finding]:
        decl = cfg.project.document(doc.prefix)
        if decl is None:
            return []  # reported once per document
        out: list[Finding] = []
        loc, uid = item.path, item.uid
        if not re.fullmatch(rf"{re.escape(doc.prefix)}{re.escape(doc.sep)}[0-9]+", uid):
            out.append(
                Finding(
                    "RVS-ITEM-NAME",
                    Severity.ERROR,
                    f"The item file {loc} is named {uid}, which is not an item ID of document {doc.prefix} "
                    f"(expected {doc.prefix}{doc.sep}0001 style).",
                    "Rename or remove the file (an Explorer 'copy of' file or an item from another document is the usual cause).",
                    loc,
                )
            )

        if item.duplicate_keys:
            out.append(
                Finding(
                    "RVS-ITEM-DUPLICATE-KEY",
                    Severity.ERROR,
                    f"Item {uid} has the key(s) {', '.join(item.duplicate_keys)} more than once; only the last one is used.",
                    "Remove the extra line(s) in the item file (a Git merge that went wrong is the usual cause).",
                    loc,
                    uid,
                )
            )

        version = item.attrs.get(VERSION_KEY)
        if version is None:
            out.append(
                Finding(
                    "RVS-SCHEMA-MISSING",
                    Severity.WARNING,
                    f"Item {uid} has no '{VERSION_KEY}' (created outside RVS?); it is treated as the current version.",
                    f"Add '{VERSION_KEY}: 1' to the item file.",
                    loc,
                    uid,
                )
            )
        else:
            try:
                _, found = migrate("item", {VERSION_KEY: version}, path=loc)
                if found < cfg_version():
                    out.append(
                        Finding(
                            "RVS-SCHEMA-OLDER",
                            Severity.INFO,
                            f"Item {uid} is schema version {found}; migrated in memory.",
                            "Save the item to write the current version.",
                            loc,
                            uid,
                        )
                    )
            except SchemaVersionError as exc:
                return [Finding(exc.code, Severity.ERROR, str(exc), "", loc, uid)]

        defs = cfg.attribute_defs(decl.kind)
        for name, value in item.attrs.items():
            adef = defs.get(name)
            if adef is None:
                out.append(
                    Finding(
                        "RVS-ATTR-UNKNOWN",
                        Severity.WARNING,
                        f"Item {uid} has attribute '{name}' that the '{decl.kind}' template does not define.",
                        f"Declare '{name}' under free_attributes in rvs-project.yaml, or remove it from the item.",
                        loc,
                        uid,
                    )
                )
                continue
            if value is None or value == "":
                continue  # unset; required/rule checks handle missing values
            if not _type_ok(adef.type, value):
                out.append(
                    Finding(
                        "RVS-ATTR-TYPE",
                        Severity.ERROR,
                        f"Attribute '{name}' of {uid} has the wrong type ({value!r}).",
                        f"Use {_TYPE_HINT[adef.type]}.",
                        loc,
                        uid,
                    )
                )
            elif adef.type == "enum" and adef.vocab and value not in cfg.vocab.values(adef.vocab):
                allowed = ", ".join(cfg.vocab.values(adef.vocab))
                out.append(
                    Finding(
                        "RVS-ATTR-VOCAB",
                        Severity.ERROR,
                        f"Attribute '{name}' of {uid} is '{value}', which is not in the project vocabulary.",
                        f"Allowed values: {allowed}.",
                        loc,
                        uid,
                    )
                )
        if item.normative and item.active:
            for name, adef in defs.items():
                if adef.required and item.attrs.get(name) in (None, ""):
                    out.append(
                        Finding(
                            "RVS-ATTR-REQUIRED",
                            Severity.ERROR,
                            f"Item {uid} has no '{name}', which the '{decl.kind}' template requires.",
                            f"Set '{name}' on the item.",
                            loc,
                            uid,
                        )
                    )
        return out

    return check


def cfg_version() -> int:
    from rvs_core.schema.versioning import CURRENT_VERSION

    return CURRENT_VERSION


def _doorstop_finding(level: str, message: str) -> Finding:
    parts = message.split(": ", 2)
    uid = parts[1] if len(parts) > 2 and _UID.match(parts[1]) else ""
    if "no links from child document" in message:
        return Finding(
            "DOORSTOP-NO-CHILD-LINKS",
            Severity.WARNING,
            message,
            "Allocate or derive an item in the child document from it, or ignore it if no allocation is needed.",
            uid=uid,
        )
    if message.endswith(": no items"):
        return Finding(
            "DOORSTOP-EMPTY-DOCUMENT",
            Severity.INFO,
            message.replace("DOORSTOP-WARNING: ", ""),
            "Normal for a new project: add the first requirement to this document when you are ready.",
        )
    if "suspect link" in message:
        return Finding(
            "DOORSTOP-SUSPECT-LINK",
            Severity.WARNING,
            message,
            "The parent changed after this link was made: review the change, then clear the suspect link.",
            uid=uid,
        )
    if "unreviewed changes" in message or "needs initial review" in message:
        return Finding(
            "DOORSTOP-UNREVIEWED",
            Severity.INFO,
            message,
            "Informational: RVS does not use Doorstop's review feature; ignore or filter this notice.",
            uid=uid,
        )
    return Finding(
        f"DOORSTOP-{level.upper()}",
        Severity(level),
        message,
        "Fix the item or link named in the message, then validate again.",
        uid=uid,
    )


def _manifest_readable(root: Path, name: str) -> bool:
    return isinstance(read_manifest(root, name).get("items"), dict)


# Doorstop messages that RVS reports itself with its own codes (typed-link aware, no duplicates).
_REPLACED_BY_RVS = ("no links from child document", "suspect link", "linked to unknown item")


def validate_project(root: Path, *, strict: bool = False, doorstop: bool = True) -> ValidationReport:
    """Validate a project folder; never raises. Anything unexpected becomes a fatal finding (see ``_validate``)."""
    try:
        return _validate(Path(root), strict=strict, doorstop=doorstop)
    except Exception as exc:  # noqa: BLE001 - hand-edited files can break any assumption; report, do not crash
        if os.environ.get("RVS_DEBUG"):
            raise
        from rvs_core.diagnostics import save_crash_report  # noqa: PLC0415 - only on the failure path

        saved = save_crash_report(type(exc), exc, exc.__traceback__)
        where = f" A crash report (no project content) was saved to {saved}." if saved else ""
        return _fatal(
            "RVS-VALIDATION-FAILED",
            f"Validation stopped unexpectedly ({type(exc).__name__}). A file with content RVS cannot interpret is the usual cause.{where}",
            "Check the files you edited by hand most recently ('git diff' shows them). If nothing explains it, send the crash report.",
        )


def _validate(root: Path, *, strict: bool, doorstop: bool) -> ValidationReport:
    """Validate a project folder.

    ``doorstop=False`` skips Doorstop's own tree validation (slow on large projects: it re-parses every item);
    every RVS check, including link and suspect-link checks, still runs.
    """
    root = Path(root)
    if not root.is_dir():
        return _fatal("RVS-PROJECT-MISSING", f"Project folder {root} does not exist.", "Check the path.")
    try:
        cfg, findings = load_project_config(root)
    except (ConfigError, SchemaVersionError) as exc:
        code = exc.code
        return _fatal(
            code,
            str(exc),
            "Fix the file named above." if code != "RVS-SCHEMA-NEWER" else "",
            getattr(exc, "location", ""),
        )
    try:
        project = DoorstopProject.open(root)
        docs = project.documents()
        items = project.items()
        issues = project.issues() if doorstop else []
    except UnreadableItemError as exc:
        return _fatal(
            "RVS-ITEM-UNREADABLE",
            str(exc),
            "Fix the YAML syntax of the file named above (a recent hand edit is the usual cause; 'git diff' shows it), then open the project again.",
        )
    except ProjectError as exc:
        return _fatal("RVS-TREE-INVALID", str(exc), "Run 'doorstop' in the project folder for details.")

    doc_check, item_check = _doc_check(cfg), _item_check(cfg)
    for doc in docs:
        findings.extend(doc_check(doc))
    docs_by_prefix = {d.prefix: d for d in docs}
    for item in items:
        findings.extend(item_check(item, docs_by_prefix[item.document]))
    for issue in issues:
        if not any(marker in issue.message for marker in _REPLACED_BY_RVS):
            findings.append(_doorstop_finding(issue.level, issue.message))
    findings.extend(run_rules(build_context(cfg, items, docs)))
    graph = LinkGraph.build(cfg, items)
    findings.extend(validate_links(cfg, graph, items))
    try:
        findings.extend(validate_change_requests(cfg, ChangeRequestStore(root, cfg), {i.uid for i in items}))
    except SchemaVersionError as exc:
        return _fatal(exc.code, str(exc), "", "changes")
    except (ChangeRequestError, OSError, ValueError) as exc:
        findings.append(
            Finding(
                "RVS-CR-INVALID",
                Severity.ERROR,
                f"A change request file cannot be read: {exc}",
                "Fix or remove the file in changes/.",
                "changes",
            )
        )
    for baseline_name in manifest_names(root):
        if not _manifest_readable(root, baseline_name):
            findings.append(
                Finding(
                    "RVS-BASELINE-MODIFIED",
                    Severity.ERROR,
                    f"The manifest of baseline {baseline_name} cannot be read.",
                    f"Restore baselines/{baseline_name}.yaml from the tagged commit (git checkout rvs/baseline/{baseline_name} -- baselines/{baseline_name}.yaml).",
                    f"baselines/{baseline_name}.yaml",
                )
            )
            continue
        try:
            findings.extend(verify_baseline(root, baseline_name, deep=False))
        except (GitError, BaselineError):
            break  # no repository here (for example an exported copy): baselines cannot be checked
    on_disk = {d.prefix for d in docs}
    for decl in cfg.project.documents:
        if decl.prefix not in on_disk:
            findings.append(
                Finding(
                    "RVS-DOC-MISSING",
                    Severity.ERROR,
                    f"Document {decl.prefix} is declared in rvs-project.yaml but has no folder with a .doorstop.yml.",
                    f"Restore the {decl.prefix} folder from Git or remove the entry from rvs-project.yaml.",
                    "rvs-project.yaml",
                )
            )
    for tag_name in orphan_tags(root):
        findings.append(
            Finding(
                "RVS-BASELINE-NOMANIFEST",
                Severity.ERROR,
                f"Baseline {tag_name} has a Git tag but its manifest baselines/{tag_name}.yaml is missing.",
                f"Restore it from the tagged commit (git checkout rvs/baseline/{tag_name} -- baselines/{tag_name}.yaml); "
                "without it the baseline is not enforced.",
                f"baselines/{tag_name}.yaml",
            )
        )
    pending = cfg.standards.unresolved()
    if pending:
        findings.append(
            Finding(
                "RVS-STD-PLACEHOLDER",
                Severity.INFO,
                f"{len(pending)} standard/company value(s) are still placeholders: {', '.join(sorted(pending))}.",
                "Fill them in config/standards.yaml when the source text is available.",
                "config/standards.yaml",
            )
        )

    findings = sort_findings(findings)
    exit_code = 0
    if any(f.code in FATAL_CODES for f in findings):
        exit_code = 3
    elif any(f.severity is Severity.ERROR for f in findings) or (
        strict and any(f.severity is Severity.WARNING for f in findings)
    ):
        exit_code = 1
    return ValidationReport(findings, exit_code, cfg, items, docs, graph)

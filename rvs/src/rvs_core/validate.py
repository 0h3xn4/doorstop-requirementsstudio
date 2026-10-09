"""``rvs validate``: schema versions, configuration, RVS attribute rules, and Doorstop's own tree validation."""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from rvs_core.adapter import DocumentInfo, DoorstopProject, ItemData, ProjectError
from rvs_core.config import ConfigError, ProjectConfig, load_project_config
from rvs_core.findings import Finding, Severity, sort_findings
from rvs_core.schema.versioning import VERSION_KEY, SchemaVersionError, migrate

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
    }
)
_UID = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)
    exit_code: int = 0
    config: ProjectConfig | None = None

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)


def _fatal(code: str, message: str, hint: str, location: str = "") -> ValidationReport:
    return ValidationReport([Finding(code, Severity.ERROR, message, hint, location)], 3)


def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def _type_ok(kind: str, value: Any) -> bool:
    if kind in ("string", "text", "enum"):
        return _is_str(value)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "date":
        return isinstance(value, date) or (_is_str(value) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None)
    if kind == "string-list":
        return isinstance(value, list) and all(_is_str(v) for v in value)
    if kind == "uid-list":
        return isinstance(value, list) and all(_is_str(v) and _UID.match(v) for v in value)
    if kind == "ref-list":
        return isinstance(value, list) and all(
            isinstance(v, dict) and set(v) == {"docno", "revision"} and all(_is_str(x) for x in v.values())
            for v in value
        )
    return False


_TYPE_HINT = {
    "string": "text",
    "text": "text",
    "enum": "one of the allowed values",
    "int": "a whole number",
    "date": "a date written YYYY-MM-DD",
    "string-list": "a list of text values",
    "uid-list": "a list of item IDs such as SYS-0001",
    "ref-list": "a list of {docno, revision} entries",
}


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
            if value is None:
                continue
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
    if "unreviewed changes" in message:
        return Finding(
            "DOORSTOP-UNREVIEWED",
            Severity.INFO,
            message,
            "Review the item to record the current text as approved.",
            uid=uid,
        )
    return Finding(
        f"DOORSTOP-{level.upper()}",
        Severity(level),
        message,
        "Fix the item or link named in the message, then validate again.",
        uid=uid,
    )


def validate_project(root: Path, *, strict: bool = False) -> ValidationReport:
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
        issues = project.issues(item_check=_item_check(cfg), doc_check=_doc_check(cfg))
    except ProjectError as exc:
        return _fatal("RVS-TREE-INVALID", str(exc), "Run 'doorstop' in the project folder for details.")

    for issue in issues:
        findings.append(issue.finding if issue.finding else _doorstop_finding(issue.level, issue.message))
    on_disk = {d.prefix for d in project.documents()}
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
    return ValidationReport(findings, exit_code, cfg)

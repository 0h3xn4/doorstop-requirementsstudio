"""Load, version-check, migrate and schema-validate the project file and config/*.yaml."""

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from rvs_core.config.model import (
    AttributeDef,
    DocumentDecl,
    KindTemplate,
    Numbering,
    ProjectConfig,
    ProjectFile,
    Standards,
    Templates,
    Vocab,
    check_document_tree,
)
from rvs_core.config.schema import ConfigError, validate_against_schema
from rvs_core.findings import Finding, Severity
from rvs_core.schema.versioning import migrate

PROJECT_FILE = "rvs-project.yaml"
# Doorstop's own item fields; an extended attribute with one of these names would overwrite them.
RESERVED_ATTRIBUTES = frozenset(
    {"level", "active", "normative", "derived", "reviewed", "text", "ref", "references", "links", "header"}
)
CONFIG_NAMES = ("numbering", "vocab", "templates", "rules", "exports", "standards")


def _parse(text: str, source: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"{source} is not valid YAML ({exc}). Fix the syntax and retry.", "RVS-CONFIG-YAML", source
        ) from None
    if not isinstance(data, dict):
        raise ConfigError(f"{source} must contain a mapping of settings at the top level.", "RVS-CONFIG-YAML", source)
    return data


def packaged_default(name: str) -> dict[str, Any]:
    text = resources.files("rvs_core.config").joinpath(f"defaults/{name}.yaml").read_text(encoding="utf-8")
    return _parse(text, f"default {name}.yaml")


def _load_one(name: str, path: Path, relative: str, findings: list[Finding], *, default_ok: bool) -> dict[str, Any]:
    if path.is_file():
        data = _parse(path.read_text(encoding="utf-8"), relative)
    elif default_ok:
        findings.append(
            Finding(
                "RVS-CONFIG-DEFAULTED",
                Severity.INFO,
                f"{relative} not found; using the packaged default.",
                "Copy the default into the project's config folder to customise it.",
                relative,
            )
        )
        data = packaged_default(name)
    else:
        raise ConfigError(f"{relative} is missing.", "RVS-PROJECT-MISSING", relative)
    data, found = migrate(name, data, path=relative)
    if found < data["rvs_schema_version"]:
        findings.append(
            Finding(
                "RVS-SCHEMA-OLDER",
                Severity.INFO,
                f"{relative} is schema version {found}; migrated in memory.",
                "Save the project to write the current version.",
                relative,
            )
        )
    validate_against_schema(name, data, source=relative)
    return data


def _attr(raw: dict[str, Any]) -> AttributeDef:
    return AttributeDef(raw["name"], raw["type"], raw.get("vocab"), bool(raw.get("required", False)))


def _check_reserved(names: list[str], source: str) -> None:
    clash = sorted(set(names) & RESERVED_ATTRIBUTES)
    if clash:
        raise ConfigError(
            f"{source}: attribute name(s) {', '.join(clash)} are reserved by Doorstop for its own item fields. "
            "Choose another name, e.g. prefix it with 'verify_'.",
            location=source,
        )


def load_project_config(root: Path) -> tuple[ProjectConfig, list[Finding]]:
    """Load everything; raises ``ConfigError`` or ``SchemaVersionError`` when the project cannot be used."""
    findings: list[Finding] = []
    raw = _load_one("project", root / PROJECT_FILE, PROJECT_FILE, findings, default_ok=False)
    docs = tuple(DocumentDecl(d["prefix"], d["kind"], d["title"], d.get("parent")) for d in raw["documents"])
    check_document_tree(docs)
    project = ProjectFile(raw["name"], docs, tuple(_attr(a) for a in raw.get("free_attributes", [])))
    _check_reserved([a.name for a in project.free_attributes], PROJECT_FILE)

    loaded = {
        n: _load_one(n, root / "config" / f"{n}.yaml", f"config/{n}.yaml", findings, default_ok=True)
        for n in CONFIG_NAMES
    }

    num = loaded["numbering"]
    numbering = Numbering(num["sep"], num["digits"], num.get("documents", {}))
    vocab = Vocab({k: tuple(v) for k, v in loaded["vocab"]["values"].items()})
    kinds = {
        k: KindTemplate(
            dict(v.get("defaults", {})), tuple(sorted(v["fingerprint"])), tuple(_attr(a) for a in v["attributes"])
        )
        for k, v in loaded["templates"]["kinds"].items()
    }
    for kind, tpl in kinds.items():
        names = {a.name for a in tpl.attributes}
        _check_reserved(sorted(names), "config/templates.yaml")
        for fp in tpl.fingerprint:
            if fp not in names:
                raise ConfigError(
                    f"config/templates.yaml: kind '{kind}' lists fingerprint attribute '{fp}' that is not in its attributes.",
                    location="config/templates.yaml",
                )
        for a in tpl.attributes:
            if a.type == "enum" and (a.vocab is None or not vocab.has(a.vocab)):
                raise ConfigError(
                    f"config/templates.yaml: attribute '{a.name}' uses unknown vocabulary '{a.vocab}'. "
                    "Add it to config/vocab.yaml or fix the name.",
                    location="config/templates.yaml",
                )
    cfg = ProjectConfig(
        project,
        numbering,
        vocab,
        Templates(kinds),
        loaded["rules"],
        loaded["exports"],
        Standards(tuple(loaded["standards"]["placeholders"])),
    )
    return cfg, findings

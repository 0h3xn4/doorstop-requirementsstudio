"""Typed, validated view of the RVS configuration files."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rvs_core.config.schema import ConfigError


@dataclass(frozen=True)
class DocumentDecl:
    prefix: str
    kind: str
    title: str
    parent: str | None = None


@dataclass(frozen=True)
class AttributeDef:
    name: str
    type: str
    vocab: str | None = None
    required: bool = False


@dataclass(frozen=True)
class ProjectFile:
    name: str
    documents: tuple[DocumentDecl, ...]
    free_attributes: tuple[AttributeDef, ...] = ()

    def document(self, prefix: str) -> DocumentDecl | None:
        return next((d for d in self.documents if d.prefix == prefix), None)


def check_document_tree(documents: tuple[DocumentDecl, ...]) -> None:
    """Doorstop trees have exactly one root document (DEVIATIONS V07)."""
    prefixes = [d.prefix for d in documents]
    dupes = sorted({p for p in prefixes if prefixes.count(p) > 1})
    if dupes:
        raise ConfigError(f"rvs-project.yaml: document prefix declared twice: {', '.join(dupes)}.")
    roots = [d.prefix for d in documents if d.parent is None]
    if len(roots) != 1:
        raise ConfigError(
            f"rvs-project.yaml: the document tree needs exactly one root document (no 'parent'), found "
            f"{len(roots)}: {', '.join(roots) or 'none'}. Make derived documents such as verification plans "
            "children of a requirements document."
        )
    for d in documents:
        if d.parent is not None and d.parent not in prefixes:
            raise ConfigError(f"rvs-project.yaml: document {d.prefix} has unknown parent {d.parent}.")
    for d in documents:
        seen = {d.prefix}
        cur = d
        while cur.parent is not None:
            if cur.parent in seen:
                raise ConfigError(f"rvs-project.yaml: document {d.prefix} is part of a parent cycle.")
            seen.add(cur.parent)
            cur = next(x for x in documents if x.prefix == cur.parent)


@dataclass(frozen=True)
class Numbering:
    sep: str
    digits: int
    overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def sep_for(self, prefix: str) -> str:
        return str(self.overrides.get(prefix, {}).get("sep", self.sep))

    def digits_for(self, prefix: str) -> int:
        return int(self.overrides.get(prefix, {}).get("digits", self.digits))


@dataclass(frozen=True)
class Vocab:
    _values: Mapping[str, tuple[str, ...]]

    def values(self, key: str) -> tuple[str, ...]:
        return self._values[key]

    def has(self, key: str) -> bool:
        return key in self._values


@dataclass(frozen=True)
class KindTemplate:
    defaults: Mapping[str, Any]
    fingerprint: tuple[str, ...]  # sorted, as Doorstop stores it
    attributes: tuple[AttributeDef, ...]

    def attribute(self, name: str) -> AttributeDef | None:
        return next((a for a in self.attributes if a.name == name), None)


@dataclass(frozen=True)
class Templates:
    kinds: Mapping[str, KindTemplate]


@dataclass(frozen=True)
class Standards:
    placeholders: tuple[Mapping[str, Any], ...]

    def unresolved(self) -> dict[str, Any]:
        return {p["id"]: p["value"] for p in self.placeholders if p["status"] != "resolved"}


@dataclass(frozen=True)
class Glossary:
    terms: tuple[tuple[str, str], ...]
    acronyms: Mapping[str, str]


@dataclass(frozen=True)
class LinkTypeDef:
    name: str
    attribute: str
    source_kinds: tuple[str, ...]
    target_kinds: tuple[str, ...]
    symmetric: bool = False


@dataclass(frozen=True)
class ProjectConfig:
    project: ProjectFile
    numbering: Numbering
    vocab: Vocab
    templates: Templates
    rules: Mapping[str, Any]
    exports: Mapping[str, Any]
    standards: Standards
    glossary: Glossary
    links: Mapping[str, LinkTypeDef]

    def attribute_defs(self, kind: str) -> dict[str, AttributeDef]:
        defs = {a.name: a for a in self.templates.kinds[kind].attributes}
        defs.update({a.name: a for a in self.project.free_attributes})
        return defs

"""Plain data types of the adapter (no Doorstop import)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rvs_core.findings import Finding


class ProjectError(Exception):
    """A project operation failed; the message says what, where and what to do."""


class UnreadableItemError(ProjectError):
    """An item or document file cannot be parsed (typically a hand-edit that broke the YAML)."""


@dataclass(frozen=True)
class DocumentInfo:
    prefix: str
    parent: str | None
    path: str
    sep: str
    digits: int
    itemformat: str
    defaults: Mapping[str, Any]
    fingerprint: tuple[str, ...]


@dataclass(frozen=True)
class ItemData:
    uid: str
    document: str
    level: str
    text: str
    header: str
    normative: bool
    derived: bool
    active: bool
    reviewed: bool
    ref: str
    links: tuple[str, ...]  # Doorstop parent links
    stamp: str = ""  # Doorstop fingerprint of this item (text, ref, fingerprint attributes)
    link_stamps: Mapping[str, str] = field(default_factory=dict)  # parent uid -> stamp recorded when last reviewed
    attrs: Mapping[str, Any] = field(default_factory=dict)  # RVS extended attributes
    path: str = ""  # relative to the project folder

    @property
    def level_key(self) -> tuple[int, ...]:
        """Sort key for the dotted level ("1.10" after "1.9"); headings (x.0) sort first."""
        try:
            return tuple(int(p) for p in self.level.split("."))
        except ValueError:
            return (10**9,)


@dataclass(frozen=True)
class Issue:
    """A Doorstop-reported issue, or an RVS finding produced by a validation hook."""

    level: str  # error | warning | info
    message: str
    finding: Finding | None = None

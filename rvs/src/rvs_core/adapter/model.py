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
    duplicate_keys: tuple[str, ...] = ()  # keys that appear twice in the item file (the last one silently wins)

    @property
    def level_key(self) -> tuple[int, ...]:
        """Sort key for the dotted level: numeric ("1.10" after "1.9"), and a heading ("6.0", "1.2.0") before the items
        of its section, including a plain "6" (Doorstop treats "6" and "6.0" as the same position)."""
        try:
            parts = [int(p) for p in self.level.split(".")]
        except ValueError:
            return (10**9,)
        if len(parts) > 1 and parts[-1] == 0:
            return (*parts[:-1], -1)
        return (*parts, 0)


@dataclass(frozen=True)
class Issue:
    """A Doorstop-reported issue, or an RVS finding produced by a validation hook."""

    level: str  # error | warning | info
    message: str
    finding: Finding | None = None

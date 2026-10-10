"""Editing with accountability: every edit records who, when and why in a per-item, append-only history file.

History files (``history/<PREFIX>/<UID>.jsonl``) hold field *names*, never field values: values live in the
item file and its Git history. One file per item keeps parallel work on different items merge-friendly.
"""

import getpass
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from rvs_core import textcheck
from rvs_core.adapter import DoorstopProject, ItemData
from rvs_core.attrtypes import TYPE_HINT, type_ok
from rvs_core.changecontrol.changes import ChangeRequestError, ChangeRequestStore
from rvs_core.changecontrol.manifests import baselined_uids
from rvs_core.config import load_project_config

HISTORY_DIR = "history"


class ReasonRequiredError(Exception):
    """The item is in a status that requires a reason for every edit."""


def _ends_with_newline(path: Path) -> bool:
    with path.open("rb") as fh:
        fh.seek(-1, 2)
        return fh.read(1) == b"\n"


def history_path(root: Path, uid: str) -> Path:
    prefix = uid.rsplit("-", 1)[0]
    return root / HISTORY_DIR / prefix / f"{uid}.jsonl"


def read_history(root: Path, uid: str) -> list[dict[str, Any]]:
    path = history_path(root, uid)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line) if line.strip() else None
        except ValueError:
            continue  # a half-written line or a merge-conflict marker must not hide the rest of the history
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no login name available (locked-down hosts); never fail an edit for this
        return "unknown"


class EditService:
    def __init__(self, root: Path, user: str | None = None, change_request: str | None = None) -> None:
        self.root = Path(root)
        self.user = user or _os_user()
        self._cfg, _ = load_project_config(self.root)
        self._baselined: set[str] | None = None
        self.change_request = change_request
        if change_request:
            try:
                cr = ChangeRequestStore(self.root, self._cfg).get(change_request)
            except ChangeRequestError as exc:
                raise ValueError(str(exc)) from exc
            if cr.status not in self._cfg.changes.open_statuses:
                raise ValueError(
                    f"{change_request} is {cr.status}, so edits cannot be attributed to it. Choose a change request whose status is open, in-review or approved."
                )

    # helpers ################################################################
    def record(self, uid: str, action: str, fields: Sequence[str], why: str) -> None:
        path = history_path(self.root, uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "action": action,
            "who": self.user,
            "when": datetime.now().astimezone().isoformat(timespec="seconds"),
            "why": why.strip(),
            "fields": sorted(fields),
        }
        if self.change_request:
            entry["cr"] = self.change_request
        with path.open("a+", encoding="utf-8", newline="\n") as fh:
            if path.stat().st_size and not _ends_with_newline(path):
                fh.write("\n")  # keep the entry off the end of an unterminated line
            fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")

    def _check_parents(self, proj: DoorstopProject, prefix: str, parents: Sequence[str]) -> None:
        doc = next((d for d in proj.documents() if d.prefix == prefix), None)
        if doc is None:
            raise ValueError(f"The document '{prefix}' does not exist in this project.")
        for uid in parents:
            try:
                parent = proj.get_item(uid)
            except Exception as exc:
                raise ValueError(f"Parent {uid} does not exist. Check the ID.") from exc
            if parent.document != doc.parent:
                raise ValueError(
                    f"{uid} is in {parent.document}, but the parent document of {prefix} is {doc.parent or 'none'}. "
                    "Choose a parent from the parent document."
                )

    def require_reason(self, item: ItemData, why: str) -> None:
        if why.strip():
            return
        statuses = self._cfg.rules.get("change_control", {}).get("reason_required_statuses", [])
        if self._baselined is None:
            self._baselined = baselined_uids(self.root)
        if item.attrs.get("status") in statuses:
            raise ReasonRequiredError(
                f"{item.uid} is {item.attrs.get('status')}; every change needs a reason. Give the reason (the Reason box in the editor, --reason on the command line)."
            )
        if item.uid in self._baselined:
            raise ReasonRequiredError(
                f"{item.uid} is part of a baseline; every change needs a reason. Give the reason (the Reason box in the editor, --reason on the command line)."
            )

    def _check_values(self, prefix: str, attrs: Mapping[str, Any], text: str | None = None) -> None:
        """Reject what must not reach an item file: unstorable characters, fields that are not part of the document's
        template (Doorstop's own fields such as links or level among them), and values outside the vocabulary."""
        decl = self._cfg.project.document(prefix)
        if decl is None:
            raise ValueError(
                f"The document '{prefix}' does not exist in this project. Choose one of: {', '.join(d.prefix for d in self._cfg.project.documents)}."
            )  # noqa: E501
        if text is not None:
            textcheck.check("statement", text)
        defs = self._cfg.attribute_defs(decl.kind)
        for name, value in attrs.items():
            if name not in defs:
                raise ValueError(
                    f"'{name}' is not a field of {prefix} items. Use the template fields: {', '.join(sorted(defs))}."
                )  # noqa: E501
            textcheck.check(name, value)
            adef = defs.get(name)
            if adef is not None and value not in (None, "", []) and not type_ok(adef.type, value):
                raise ValueError(f"'{name}' must be {TYPE_HINT.get(adef.type, adef.type)}; got {value!r}.")
            if adef is not None and adef.type == "enum" and adef.vocab and value not in (None, ""):
                allowed = self._cfg.vocab.values(adef.vocab)
                if value not in allowed:
                    raise ValueError(f"'{value}' is not allowed for {name}. Use one of: {', '.join(allowed)}.")

    # operations #############################################################
    def create_item(
        self,
        prefix: str,
        text: str,
        *,
        attrs: Mapping[str, Any] | None = None,
        parents: Sequence[str] = (),
        derived: bool = False,
        why: str = "",
    ) -> ItemData:
        proj = DoorstopProject.open(self.root)
        self._check_values(prefix, attrs or {}, text)
        self._check_parents(proj, prefix, parents)
        history_path(self.root, f"{prefix}-0").parent.mkdir(parents=True, exist_ok=True)  # fail before writing
        decl = self._cfg.project.document(prefix)
        defaults = dict(self._cfg.templates.kinds[decl.kind].defaults) if decl else {}
        item = proj.add_item(prefix, text, attrs={**defaults, **(attrs or {})}, derived=derived)
        for parent in parents:
            proj.link(item.uid, parent)
        self.record(item.uid, "create", ["text", *(attrs or {}), *(["links"] if parents else [])], why)
        return proj.get_item(item.uid)

    def update_item(
        self, uid: str, *, text: str | None = None, attrs: Mapping[str, Any] | None = None, why: str = ""
    ) -> ItemData:
        proj = DoorstopProject.open(self.root)
        before = proj.get_item(uid)
        self._check_values(before.document, attrs or {}, text)
        self.require_reason(before, why)
        history_path(self.root, uid).parent.mkdir(parents=True, exist_ok=True)  # fail before writing, not after
        changed = [k for k, v in (attrs or {}).items() if before.attrs.get(k) != v]
        if text is not None and text.strip() != before.text.strip():
            changed.append("text")
        if not changed:
            return before
        proj.update_item(
            uid, text=text if "text" in changed else None, attrs={k: (attrs or {})[k] for k in changed if k != "text"}
        )
        self.record(uid, "update", changed, why)
        return proj.get_item(uid)

    def clear_suspect(self, uid: str, *, why: str = "") -> ItemData:
        """Accept the current state of the item's parents: its links stop being suspect."""
        proj = DoorstopProject.open(self.root)
        before = proj.get_item(uid)
        self.require_reason(before, why)
        if not proj.suspect_links(uid):
            return before
        history_path(self.root, uid).parent.mkdir(parents=True, exist_ok=True)
        proj.clear_suspect(uid)
        self.record(uid, "clear-suspect", ["links"], why)
        return proj.get_item(uid)

    def set_parents(self, uid: str, parents: Sequence[str], *, why: str = "") -> ItemData:
        proj = DoorstopProject.open(self.root)
        before = proj.get_item(uid)
        self.require_reason(before, why)
        self._check_parents(proj, before.document, parents)
        if tuple(sorted(parents)) == before.links:
            return before
        history_path(self.root, uid).parent.mkdir(parents=True, exist_ok=True)
        proj.set_links(uid, parents)
        self.record(uid, "update", ["links"], why)
        return proj.get_item(uid)

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

from rvs_core.adapter import DoorstopProject, ItemData
from rvs_core.config import load_project_config

HISTORY_DIR = "history"


class ReasonRequiredError(Exception):
    """The item is in a status that requires a reason for every edit."""


def history_path(root: Path, uid: str) -> Path:
    prefix = uid.rsplit("-", 1)[0]
    return root / HISTORY_DIR / prefix / f"{uid}.jsonl"


def read_history(root: Path, uid: str) -> list[dict[str, Any]]:
    path = history_path(root, uid)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no login name available (locked-down hosts); never fail an edit for this
        return "unknown"


class EditService:
    def __init__(self, root: Path, user: str | None = None) -> None:
        self.root = Path(root)
        self.user = user or _os_user()
        self._cfg, _ = load_project_config(self.root)

    # helpers ################################################################
    def _record(self, uid: str, action: str, fields: Sequence[str], why: str) -> None:
        path = history_path(self.root, uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "action": action,
            "who": self.user,
            "when": datetime.now().astimezone().isoformat(timespec="seconds"),
            "why": why.strip(),
            "fields": sorted(fields),
        }
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")

    def _check_parents(self, proj: DoorstopProject, prefix: str, parents: Sequence[str]) -> None:
        doc = next(d for d in proj.documents() if d.prefix == prefix)
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

    def _require_reason(self, item: ItemData, why: str) -> None:
        statuses = self._cfg.rules.get("change_control", {}).get("reason_required_statuses", [])
        if item.attrs.get("status") in statuses and not why.strip():
            raise ReasonRequiredError(
                f"{item.uid} is {item.attrs.get('status')}; every change needs a reason. Enter why you are changing it."
            )

    # operations #############################################################
    def create_item(
        self,
        prefix: str,
        text: str,
        *,
        attrs: Mapping[str, Any] | None = None,
        parents: Sequence[str] = (),
        why: str = "",
    ) -> ItemData:
        proj = DoorstopProject.open(self.root)
        self._check_parents(proj, prefix, parents)
        item = proj.add_item(prefix, text, attrs=attrs)
        for parent in parents:
            proj.link(item.uid, parent)
        self._record(item.uid, "create", ["text", *(attrs or {}), *(["links"] if parents else [])], why)
        return proj.get_item(item.uid)

    def update_item(
        self, uid: str, *, text: str | None = None, attrs: Mapping[str, Any] | None = None, why: str = ""
    ) -> ItemData:
        proj = DoorstopProject.open(self.root)
        before = proj.get_item(uid)
        self._require_reason(before, why)
        changed = [k for k, v in (attrs or {}).items() if before.attrs.get(k) != v]
        if text is not None and text.strip() != before.text.strip():
            changed.append("text")
        if not changed:
            return before
        proj.update_item(
            uid, text=text if "text" in changed else None, attrs={k: (attrs or {})[k] for k in changed if k != "text"}
        )
        self._record(uid, "update", changed, why)
        return proj.get_item(uid)

    def set_parents(self, uid: str, parents: Sequence[str], *, why: str = "") -> ItemData:
        proj = DoorstopProject.open(self.root)
        before = proj.get_item(uid)
        self._require_reason(before, why)
        self._check_parents(proj, before.document, parents)
        if tuple(sorted(parents)) == before.links:
            return before
        proj.set_links(uid, parents)
        self._record(uid, "update", ["links"], why)
        return proj.get_item(uid)

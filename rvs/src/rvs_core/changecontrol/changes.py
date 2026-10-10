"""Change requests: ``changes/CR-0001.yaml``. They group edits, carry a status and name the affected items."""

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from rvs_core.config import ProjectConfig
from rvs_core.findings import Finding, Severity
from rvs_core.schema.versioning import CURRENT_VERSION, migrate

CHANGES_DIR = "changes"


class ChangeRequestError(Exception):
    """A change request operation failed; the message says what to do."""


@dataclass(frozen=True)
class ChangeRequest:
    id: str
    title: str
    description: str
    status: str
    raised_by: str
    items: tuple[str, ...] = ()
    log: tuple[dict[str, Any], ...] = ()


StrList = list[str]
CRList = list[ChangeRequest]  # the store has a method called list, which shadows the builtin in its body


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ChangeRequestStore:
    def __init__(self, root: Path, cfg: ProjectConfig) -> None:
        self.root, self.cfg = Path(root), cfg
        self.dir = self.root / CHANGES_DIR

    # reading ##################################################################
    def _path(self, cr_id: str) -> Path:
        if not re.fullmatch(r"CR-[0-9]+", cr_id):
            raise ChangeRequestError(f"'{cr_id}' is not a change request ID such as CR-0001.")
        return self.dir / f"{cr_id}.yaml"

    def _read(self, path: Path) -> ChangeRequest:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ChangeRequestError(f"{CHANGES_DIR}/{path.name} must contain a mapping of settings.")
        data, _ = migrate("change_request", raw, path=f"{CHANGES_DIR}/{path.name}")
        return ChangeRequest(
            id=str(data.get("id", path.stem)),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            status=str(data.get("status", "")),
            raised_by=str(data.get("raised_by", "")),
            items=tuple(str(i) for i in data.get("items") or []),
            log=tuple(dict(e) for e in data.get("log") or []),
        )

    def list(self) -> CRList:
        if not self.dir.is_dir():
            return []
        return [self._read(p) for p in sorted(self.dir.iterdir()) if re.fullmatch(r"CR-[0-9]+\.yaml", p.name)]

    def get(self, cr_id: str) -> ChangeRequest:
        path = self._path(cr_id)
        if not path.is_file():
            raise ChangeRequestError(f"Change request {cr_id} does not exist. Check the ID.")
        return self._read(path)

    def open_requests(self) -> CRList:
        """Requests that block a baseline: the open statuses, and any status the configuration does not define (a typo
        must not let a request slip past the gate; RVS-CR-STATUS reports it)."""
        defined = set(self.cfg.changes.statuses)
        return [c for c in self.list() if c.status in self.cfg.changes.open_statuses or c.status not in defined]

    def edited_items(self, cr_id: str) -> StrList:
        """Items that have history entries attributed to this change request."""
        found: set[str] = set()
        for path in (self.root / "history").glob("*/*.jsonl") if (self.root / "history").is_dir() else []:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    entry = json.loads(line) if line.strip() else None
                except ValueError:
                    continue  # a damaged line must not hide the rest of the history
                if isinstance(entry, dict) and entry.get("cr") == cr_id:
                    found.add(path.stem)
        return sorted(found)

    # writing ##################################################################
    def _dump(self, cr: ChangeRequest) -> str:
        data = {
            "rvs_schema_version": CURRENT_VERSION,
            "id": cr.id,
            "title": cr.title,
            "description": cr.description,
            "status": cr.status,
            "raised_by": cr.raised_by,
            "items": sorted(cr.items),
            "log": [dict(e) for e in cr.log],
        }
        return yaml.safe_dump(data, sort_keys=True, allow_unicode=True)

    def _write(self, cr: ChangeRequest) -> None:
        self.dir.mkdir(exist_ok=True)
        self._atomic_write(self._path(cr.id), self._dump(cr), replace=True)

    def _atomic_write(self, path: Path, text: str, *, replace: bool) -> bool:
        """Write via a temporary file, so a reader never sees half a file. With ``replace=False`` an existing file is
        left alone and False is returned (two creators can never share an ID)."""
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        try:
            if replace:
                os.replace(tmp, path)
                return True
            try:
                os.link(tmp, path)  # fails if the file exists: atomic "create only"
            except FileExistsError:
                return False
            return True
        finally:
            tmp.unlink(missing_ok=True)

    def create(
        self, title: str, description: str, raised_by: str, items: StrList | tuple[str, ...] = ()
    ) -> ChangeRequest:
        if not title.strip():
            raise ChangeRequestError("A change request needs a title.")
        first = self.cfg.changes.statuses[0]
        self.dir.mkdir(exist_ok=True)
        while True:
            numbers = [int(c.id.split("-")[1]) for c in self.list() if c.id.split("-")[-1].isdigit()]
            cr_id = f"CR-{max(numbers, default=0) + 1:0{self.cfg.changes.digits}d}"
            cr = ChangeRequest(cr_id, title.strip(), description, first, raised_by, tuple(items),
                               ({"when": _now(), "who": raised_by, "status": first, "note": "created"},))  # fmt: skip
            if self._atomic_write(self._path(cr_id), self._dump(cr), replace=False):
                return cr  # otherwise someone else just took this number: pick the next one

    def update(
        self,
        cr_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        items: StrList | tuple[str, ...] | None = None,
        who: str = "",
    ) -> ChangeRequest:
        cr = self.get(cr_id)
        new = ChangeRequest(
            cr.id,
            cr.title if title is None else title.strip() or cr.title,
            cr.description if description is None else description,
            cr.status,
            cr.raised_by,
            cr.items if items is None else tuple(items),
            cr.log,
        )
        self._write(new)
        return new

    def set_status(self, cr_id: str, status: str, who: str, note: str = "") -> ChangeRequest:
        if status not in self.cfg.changes.statuses:
            raise ChangeRequestError(
                f"'{status}' is not a change request status. Use one of: {', '.join(self.cfg.changes.statuses)}."
            )
        cr = self.get(cr_id)
        entry = {"when": _now(), "who": who, "status": status, "note": note}
        new = ChangeRequest(cr.id, cr.title, cr.description, status, cr.raised_by, cr.items, (*cr.log, entry))
        self._write(new)
        return new

    def defer(self, cr_id: str, reason: str, who: str) -> ChangeRequest:
        if not reason.strip():
            raise ChangeRequestError(f"Deferring {cr_id} needs a reason; say why it can wait.")
        return self.set_status(cr_id, self.cfg.changes.deferred_status, who, reason.strip())


def validate_change_requests(cfg: ProjectConfig, store: ChangeRequestStore, uids: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for cr in store.list():
        loc = f"{CHANGES_DIR}/{cr.id}.yaml"
        if cr.status not in cfg.changes.statuses:
            findings.append(
                Finding(
                    "RVS-CR-STATUS", Severity.ERROR,
                    f"Change request {cr.id} has status '{cr.status}', which config/changes.yaml does not define.",
                    f"Use one of: {', '.join(cfg.changes.statuses)}.", loc,
                )
            )  # fmt: skip
        for uid in cr.items:
            if uid not in uids:
                findings.append(
                    Finding("RVS-CR-ITEM", Severity.WARNING, f"Change request {cr.id} lists {uid}, which does not exist.",
                            "Correct the item ID or remove it from the change request.", loc)
                )  # fmt: skip
    return findings

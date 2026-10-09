"""The open project as seen by the GUI: items, findings and edit operations. Qt signals, no widgets."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from rvs_core.adapter import DocumentInfo, ItemData
from rvs_core.authoring import EditService
from rvs_core.changecontrol.baselines import current_label
from rvs_core.changecontrol.changes import ChangeRequest, ChangeRequestError, ChangeRequestStore
from rvs_core.config import ProjectConfig
from rvs_core.findings import Finding, Severity
from rvs_core.trace import LinkGraph
from rvs_core.validate import ValidationReport, validate_project


class ProjectSession(QObject):
    loaded = Signal()  # a project was opened or fully refreshed
    item_changed = Signal(str)  # uid of the item that was created or edited (after refresh)
    active_cr_changed = Signal(object)  # change request id or None

    def __init__(self, parent: QObject | None = None, user: str | None = None) -> None:
        super().__init__(parent)
        self.root: Path | None = None
        self.cfg: ProjectConfig | None = None
        self.items: list[ItemData] = []
        self.docs: list[DocumentInfo] = []
        self.findings: list[Finding] = []
        self.graph: LinkGraph | None = None
        self.report: ValidationReport | None = None
        self.user = user
        self.active_cr: str | None = None
        self.baseline_label = "working copy"
        self._by_uid: dict[str, ItemData] = {}
        self._findings_by_uid: dict[str, list[Finding]] = {}

    # loading ##################################################################
    def open(self, root: Path) -> ValidationReport:
        """Validate and load ``root``. On a fatal problem nothing is loaded and the report explains why."""
        report = validate_project(root, doorstop=False)  # fast path: Doorstop's own validation is on request
        self.report = report
        if report.exit_code == 3 or report.config is None:
            return report
        self.root, self.cfg = Path(root), report.config
        self._load(report)
        self.loaded.emit()
        return report

    def refresh(self) -> None:
        if self.root is None:
            return
        self._apply(validate_project(self.root, doorstop=False))

    def run_full_validation(self) -> None:
        """Also run Doorstop's own tree validation (re-parses every item: slow on large projects)."""
        if self.root is not None:
            self._apply(validate_project(self.root, doorstop=True))

    def _apply(self, report: ValidationReport) -> None:
        self.report = report
        if report.config is not None and report.exit_code != 3:
            self.cfg = report.config
            self._load(report)
            self.loaded.emit()

    def _load(self, report: ValidationReport) -> None:
        assert self.root is not None
        self.docs = report.docs
        self.graph = report.graph
        self.items = sorted(report.items, key=lambda i: (self._doc_order(i.document), i.level_key, i.uid))
        self._by_uid = {i.uid: i for i in self.items}
        self.findings = report.findings
        try:
            self.baseline_label = current_label(self.root)
        except Exception:  # noqa: BLE001 - the label is cosmetic; never block loading on it
            self.baseline_label = "working copy"
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for f in self.findings:
            if f.uid:
                grouped[f.uid].append(f)
        self._findings_by_uid = dict(grouped)

    def _doc_order(self, prefix: str) -> int:
        order = [d.prefix for d in self.cfg.project.documents] if self.cfg else []
        return order.index(prefix) if prefix in order else len(order)

    # queries ##################################################################
    def item(self, uid: str) -> ItemData | None:
        return self._by_uid.get(uid)

    def findings_for(self, uid: str) -> list[Finding]:
        return self._findings_by_uid.get(uid, [])

    def kind_of(self, prefix: str) -> str:
        assert self.cfg is not None
        decl = self.cfg.project.document(prefix)
        return decl.kind if decl else "requirements"

    def requirement_documents(self) -> list[str]:
        assert self.cfg is not None
        return [d.prefix for d in self.cfg.project.documents if d.kind == "requirements"]

    # edits ####################################################################
    def _service(self) -> EditService:
        assert self.root is not None
        return EditService(self.root, user=self.user, change_request=self.active_cr)

    def update_item(
        self, uid: str, *, text: str | None = None, attrs: Mapping[str, Any] | None = None, why: str = ""
    ) -> ItemData:
        item = self._service().update_item(uid, text=text, attrs=attrs, why=why)
        self.refresh()
        self.item_changed.emit(uid)
        return item

    def set_parents(self, uid: str, parents: Sequence[str], why: str = "") -> ItemData:
        item = self._service().set_parents(uid, parents, why=why)
        self.refresh()
        self.item_changed.emit(uid)
        return item

    def create_item(
        self,
        prefix: str,
        text: str,
        *,
        attrs: Mapping[str, Any],
        parents: Sequence[str] = (),
        derived: bool = False,
        why: str = "",
    ) -> ItemData:
        item = self._service().create_item(prefix, text, attrs=attrs, parents=parents, derived=derived, why=why)
        self.refresh()
        self.item_changed.emit(item.uid)
        return item

    def clear_suspect(self, uid: str, why: str = "") -> ItemData:
        item = self._service().clear_suspect(uid, why=why)
        self.refresh()
        self.item_changed.emit(uid)
        return item

    def suspect_parents(self, uid: str) -> list[str]:
        item = self.item(uid)
        if item is None:
            return []
        return sorted(
            p for p, stamp in item.link_stamps.items() if (t := self.item(p)) is not None and stamp != t.stamp
        )

    def documents_of_kind(self, kind: str) -> list[str]:
        assert self.cfg is not None
        return [d.prefix for d in self.cfg.project.documents if d.kind == kind]

    # change requests ###########################################################
    def store(self) -> ChangeRequestStore:
        assert self.root is not None and self.cfg is not None
        return ChangeRequestStore(self.root, self.cfg)

    def change_requests(self) -> list[ChangeRequest]:
        return self.store().list() if self.root else []

    def change_request(self, cr_id: str) -> ChangeRequest | None:
        try:
            return self.store().get(cr_id)
        except ChangeRequestError:
            return None

    def set_active_cr(self, cr_id: str | None) -> None:
        """Attribute the user's edits to ``cr_id``; raises ValueError if it is unknown or no longer open."""
        if cr_id:
            EditService(self.root, user=self.user, change_request=cr_id)  # type: ignore[arg-type]  # validates
        self.active_cr = cr_id
        self.active_cr_changed.emit(cr_id)

    def counts_for(self, uid: str) -> tuple[int, int, int]:
        fs = self.findings_for(uid)
        return tuple(sum(1 for f in fs if f.severity is s) for s in (Severity.ERROR, Severity.WARNING, Severity.INFO))  # type: ignore[return-value]

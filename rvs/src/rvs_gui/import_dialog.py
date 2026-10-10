"""Import preview: what an import would create, change or reject, before anything is written."""

from collections.abc import Sequence
from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rvs_core.adapter import DoorstopProject
from rvs_core.changecontrol.manifests import baselined_uids
from rvs_core.exporters.itemsio import ImportPlan, plan_import
from rvs_core.matrices import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_gui.matrix_views import MatrixTableModel
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import keyboard_view, named, secondary


class ImportDialog(QDialog):
    def __init__(self, session: ProjectSession, rows: Sequence[dict[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.setWindowTitle("Import items")
        self.resize(820, 520)
        self.session, self.rows = session, list(rows)
        self.plan = ImportPlan()
        self.summary = QLabel()
        self.model = MatrixTableModel(self)
        self.table = named(keyboard_view(QTableView()), "Import preview")
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.reason = named(QLineEdit(), "Reason for the import")
        self.reason.setPlaceholderText("Reason for these changes (required when baselined items change)")
        self.skip_errors = QCheckBox("Import the valid rows and skip rows with errors")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setText("Import")
        secondary(self.buttons.button(QDialogButtonBox.StandardButton.Cancel))
        # read the baselines and the item files once: planning runs again for every character typed in the reason
        self._baselined: frozenset[str] | None = None
        self._all_uids: frozenset[str] | None = None
        if session.root is not None:
            try:
                self._baselined = frozenset(baselined_uids(session.root))
                self._all_uids = frozenset(DoorstopProject.open(session.root).all_uids())
            except Exception:  # noqa: BLE001 - plan_import then reads them itself
                self._baselined = self._all_uids = None
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.summary)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.reason)
        lay.addWidget(self.skip_errors)
        lay.addWidget(self.buttons)
        self.reason.textChanged.connect(self.replan)
        self.skip_errors.toggled.connect(self._update_button)
        # Tab goes preview table -> reason -> checkbox -> Import -> Cancel (the table never traps the key)
        self.setTabOrder(self.table, self.reason)
        self.setTabOrder(self.reason, self.skip_errors)
        self.setTabOrder(self.skip_errors, self.apply_button)
        self.setTabOrder(self.apply_button, self.buttons.button(QDialogButtonBox.StandardButton.Cancel))
        self.replan()

    def replan(self, *_a: Any) -> None:
        cfg = self.session.cfg
        assert cfg is not None
        self.plan = plan_import(
            cfg,
            self.session.items,
            self.rows,
            why=self.reason.text(),
            root=self.session.root,
            baselined=self._baselined,
            all_uids=self._all_uids,
        )
        rows, flags = [], []
        for r in self.plan.results:
            if r.action == "unchanged":
                continue
            detail = r.message if r.action == "error" else ", ".join(r.changes)
            rows.append([str(r.row), r.action, r.uid or "(new)", detail])
            flags.append("orphan" if r.action == "error" else None)
        prov = Provenance.now(cfg, user=self.session.user)
        self.model.set_matrix(
            MatrixTable("Import plan", ["Row", "Action", "ID", "Changes / problem"], rows, flags, prov)
        )
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        errors = len(self.plan.errors)
        self.summary.setText(
            f"{self.plan.count('create')} to create, {self.plan.count('update')} to update, "
            f"{self.plan.count('unchanged')} unchanged, {errors} error{'s' if errors != 1 else ''}."
        )
        self._update_button()

    def _update_button(self, *_a: Any) -> None:
        work = self.plan.count("create") + self.plan.count("update")
        blocked = bool(self.plan.errors) and not self.skip_errors.isChecked()
        self.apply_button.setEnabled(work > 0 and not blocked)

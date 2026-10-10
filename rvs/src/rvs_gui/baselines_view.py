"""Baselines tab: list, create (background), verify, compare."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rvs_core.changecontrol.baselines import Baseline, create_baseline, list_baselines, verify_baseline
from rvs_core.matrices import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_core.vcs.git import GitError
from rvs_gui.baseline_dialog import NewBaselineDialog
from rvs_gui.jobs import run_in_background
from rvs_gui.matrix_views import MatrixTableModel
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import keyboard_view, named, secondary


def friendly_baseline_error(exc: Exception) -> str:
    """The error as shown in the window: no command-line advice, which a user of this program cannot follow."""
    text = str(exc)
    if isinstance(exc, GitError) and "not inside a Git repository" in text:
        return (
            "This project is not under version control yet, and a baseline needs it. "
            "Press New baseline… again and tick 'Turn on version control for this project'."
        )
    return text


class BaselinesView(QWidget):
    message = Signal(str, str)
    baseline_done = Signal(str, str)  # (name, error message or '')
    compare_requested = Signal(str)  # baseline name, to be compared with the working copy

    def __init__(self, session: ProjectSession) -> None:
        super().__init__()
        self.session = session
        self.model = MatrixTableModel(self)
        self.setMinimumSize(480, 200)
        self.table = named(keyboard_view(QTableView()), "Baselines")
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.new_button = QPushButton("New baseline…")
        self.verify_button = QPushButton("Verify")
        secondary(self.verify_button)
        self.compare_button = QPushButton("Compare with working copy")
        secondary(self.compare_button)
        self.empty_hint = QLabel("No baselines yet. A baseline freezes the project at a milestone: press New baseline…")
        self.empty_hint.setObjectName("Empty")
        self.empty_hint.setWordWrap(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.verify_button)
        buttons.addWidget(self.compare_button)
        buttons.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addLayout(buttons)
        lay.addWidget(self.empty_hint)
        lay.addWidget(self.table, 1)
        self.new_button.clicked.connect(self.new_baseline_dialog)
        self.verify_button.clicked.connect(self.verify)
        self.compare_button.clicked.connect(self.compare_with_working_copy)
        session.loaded.connect(self.refresh)

    def refresh(self) -> None:
        if self.session.root is None or self.session.cfg is None:
            return
        try:
            found: list[Baseline] = list_baselines(self.session.root)
        except Exception as exc:  # noqa: BLE001 - friendly message
            self.message.emit("error", f"The baselines could not be listed: {exc}")
            return
        rows = [
            [b.name, b.created[:19].replace("T", " "), b.created_by, str(b.items), ", ".join(b.deferred), b.description]
            for b in found
        ]
        prov = Provenance.now(self.session.cfg, user=self.session.user)
        cols = ["Name", "Created", "By", "Items", "Deferred CRs", "Reason"]
        self.model.set_matrix(MatrixTable("Baselines", cols, rows, [None] * len(rows), prov))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.empty_hint.setVisible(not rows)

    def selected(self) -> str | None:
        idx = self.table.currentIndex()
        return str(self.model.index(idx.row(), 0).data()) if idx.isValid() else None

    def select(self, name: str) -> None:
        for r in range(self.model.rowCount()):
            if self.model.index(r, 0).data() == name:
                self.table.selectRow(r)

    def new_baseline_dialog(self) -> None:
        if self.session.cfg is None:
            self.message.emit("info", "Open a project first.")
            return
        if self.session.busy:
            self.message.emit("info", f"Please wait: {self.session.busy_reason}.")
            return
        dlg = NewBaselineDialog(self.session, self)
        try:
            if dlg.exec():
                name, description, defer = dlg.values()
                self.create_baseline(name, description, defer, init_git=dlg.init_git())
        finally:
            dlg.deleteLater()

    def create_baseline(self, name: str, description: str, defer: dict[str, str], init_git: bool = False) -> None:
        root, user = self.session.root, self.session.user
        if root is None:
            return
        if self.session.busy:
            self.message.emit("info", f"Please wait: {self.session.busy_reason}.")
            return
        self.session.begin_busy(f"baseline {name} is being created")  # edits are refused until the worker has finished
        self.new_button.setEnabled(False)
        self.message.emit("info", f"Creating baseline {name} … (editing is paused until it is done)")

        def finish() -> None:
            self.new_button.setEnabled(True)
            self.session.end_busy()

        def done(b: Baseline) -> None:
            finish()
            self.session.refresh()
            self.message.emit("success", f"Baseline {b.name} created: {b.items} items, tag {b.tag}.")
            self.baseline_done.emit(name, "")

        def failed(exc: Exception) -> None:
            finish()
            text = friendly_baseline_error(exc)
            self.message.emit("error", text)
            self.baseline_done.emit(name, text)

        run_in_background(
            lambda: create_baseline(root, name, description, user=user, defer=defer, init_git=init_git), done, failed
        )

    def verify(self) -> None:
        name, root = self.selected(), self.session.root
        if not name or root is None:
            self.message.emit("info", "Select a baseline first.")
            return
        try:
            findings = verify_baseline(root, name)
        except Exception as exc:  # noqa: BLE001
            self.message.emit("error", str(exc))
            return
        if findings:
            self.message.emit("error", " ".join(f"{f.message} {f.hint}" for f in findings))
        else:
            self.message.emit("success", f"Baseline {name} is intact.")

    def compare_with_working_copy(self) -> None:
        name = self.selected()
        if name:
            self.compare_requested.emit(name)
        else:
            self.message.emit("info", "Select a baseline first.")

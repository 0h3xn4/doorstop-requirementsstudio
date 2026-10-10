"""New baseline dialog: name, reason, and what to do about open change requests."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rvs_core.changecontrol.baselines import NAME_RE
from rvs_core.vcs.git import GitError, GitRepo
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import keyboard_view, named, secondary

PERMANENT_NOTE = "A baseline is permanent: it cannot be edited or deleted and its name cannot be reused."


def has_repository(root: object) -> bool:
    """True when the project folder is inside a Git repository (baselines are Git tags)."""
    try:
        GitRepo.discover(root)  # type: ignore[arg-type]
    except GitError:
        return False
    return True


class NewBaselineDialog(QDialog):
    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.setWindowTitle("New baseline")
        self.resize(560, 420)
        self.session = session
        self.name = named(QLineEdit(), "Baseline name")
        self.name.setPlaceholderText("For example PDR or SRR-2")
        self.description = named(QLineEdit(), "Reason for the baseline")
        self.description.setPlaceholderText("Why this baseline is created")
        self.open_list = named(keyboard_view(QListWidget()), "Open change requests")
        self._requests = [c for c in session.change_requests() if c.status in session.cfg.changes.open_statuses]
        self._checks: list[QCheckBox] = []
        self._reasons: list[QLineEdit] = []
        for cr in self._requests:
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(4, 2, 4, 2)
            check = QCheckBox(f"Defer {cr.id} ({cr.status}): {cr.title}")
            reason = named(QLineEdit(), f"Reason for deferring {cr.id}")
            reason.setPlaceholderText("Reason for deferring")
            row_lay.addWidget(check, 2)
            row_lay.addWidget(reason, 2)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.open_list.addItem(item)
            self.open_list.setItemWidget(item, row)
            self._checks.append(check)
            self._reasons.append(reason)
            check.toggled.connect(self._update)
            reason.textChanged.connect(self._update)
        promote = session.cfg.changes.promote
        n = sum(1 for i in session.items if i.attrs.get("status") in promote)
        targets = ", ".join(f"{a} → {b}" for a, b in promote.items())
        self.promote_note = QLabel(
            f"{n} item(s) will change status ({targets}) when the baseline is created." if promote else ""
        )
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.permanent_note = QLabel(PERMANENT_NOTE)
        self.permanent_note.setWordWrap(True)
        self.permanent_note.setObjectName("Empty")
        self.has_repo = has_repository(session.root)
        self.use_git = QCheckBox("Turn on version control for this project")
        self.use_git.setToolTip(
            "Baselines are stored as Git tags. This creates a local Git repository in the project folder."
        )
        self.git_note = QLabel(
            "This project is not under version control yet, and a baseline needs it. "
            "Tick the box to turn it on: RVS creates a local repository in the project folder (nothing is sent anywhere)."
        )
        self.git_note.setWordWrap(True)
        self.use_git.setVisible(not self.has_repo)
        self.git_note.setVisible(not self.has_repo)
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Reason", self.description)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.create_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText("Create permanent baseline")
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        secondary(cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        if self._requests:
            lay.addWidget(QLabel("Open change requests block a baseline unless they are explicitly deferred:"))
            lay.addWidget(self.open_list, 1)
        lay.addWidget(self.git_note)
        lay.addWidget(self.use_git)
        lay.addWidget(self.promote_note)
        lay.addWidget(self.permanent_note)
        lay.addWidget(self.problem)
        lay.addWidget(self.buttons)
        self.use_git.toggled.connect(self._update)
        self.name.textChanged.connect(self._update)
        self.description.textChanged.connect(self._update)
        self._update()

    def defer_checkbox(self, i: int) -> QCheckBox:
        return self._checks[i]

    def defer_reason(self, i: int) -> QLineEdit:
        return self._reasons[i]

    def values(self) -> tuple[str, str, dict[str, str]]:
        defer = {
            cr.id: self._reasons[i].text().strip() for i, cr in enumerate(self._requests) if self._checks[i].isChecked()
        }
        return self.name.text().strip(), self.description.text().strip(), defer

    def init_git(self) -> bool:
        """True when the user asked for version control to be turned on (only offered when there is none)."""
        return not self.has_repo and self.use_git.isChecked()

    def _problem(self) -> str:
        if not self.has_repo and not self.use_git.isChecked():
            return "Tick 'Turn on version control for this project': a baseline needs it."
        name = self.name.text().strip()
        if not NAME_RE.match(name):
            return (
                "The name may use letters, digits, '.', '_' and '-' (no spaces); it is required."
                if name
                else "Enter a baseline name."
            )
        if not self.description.text().strip():
            return "Say why the baseline is created."
        pending = [cr.id for i, cr in enumerate(self._requests) if not self._checks[i].isChecked()]
        if pending:
            return f"Open change requests: {', '.join(pending)}. Close them in the Changes tab, or defer them here."
        missing = [cr.id for i, cr in enumerate(self._requests) if not self._reasons[i].text().strip()]
        if missing:
            return f"Give a reason for deferring {', '.join(missing)}."
        return ""

    def _update(self, *_a: object) -> None:
        text = self._problem()
        self.problem.setText(text)
        self.create_button.setEnabled(not text)

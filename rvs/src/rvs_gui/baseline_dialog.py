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
from rvs_gui.session import ProjectSession


class NewBaselineDialog(QDialog):
    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.setWindowTitle("New baseline")
        self.resize(560, 420)
        self.session = session
        self.name = QLineEdit()
        self.name.setPlaceholderText("For example PDR or SRR-2")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Why this baseline is created")
        self.open_list = QListWidget()
        self._requests = [c for c in session.change_requests() if c.status in session.cfg.changes.open_statuses]
        self._checks: list[QCheckBox] = []
        self._reasons: list[QLineEdit] = []
        for cr in self._requests:
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(4, 2, 4, 2)
            check = QCheckBox(f"Defer {cr.id} ({cr.status}): {cr.title}")
            reason = QLineEdit()
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
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Reason", self.description)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.create_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText("Create baseline")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        if self._requests:
            lay.addWidget(QLabel("Open change requests block a baseline unless they are explicitly deferred:"))
            lay.addWidget(self.open_list, 1)
        lay.addWidget(self.promote_note)
        lay.addWidget(self.problem)
        lay.addWidget(self.buttons)
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

    def _problem(self) -> str:
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

"""Change requests tab."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rvs_core.changecontrol.changes import ChangeRequestError
from rvs_core.matrices import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_gui.matrix_views import MatrixTableModel
from rvs_gui.session import ProjectSession


def _ids(text: str) -> list[str]:
    return [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]


class ChangesView(QWidget):
    message = Signal(str, str)

    def __init__(self, session: ProjectSession) -> None:
        super().__init__()
        self.session = session
        self.current_id: str | None = None
        self.model = MatrixTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.heading = QLabel("Select a change request, or fill in the form and press New.")
        self._refreshing = False
        self._snapshot: tuple[str, str, str, str] = ("", "", "", "")
        self.title = QLineEdit()
        self.status = QComboBox()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(90)
        self.items = QLineEdit()
        self.items.setPlaceholderText("Affected item IDs, comma separated")
        self.use_for_edits = QCheckBox("Attribute my edits to this change request")
        self.edited = QListWidget()
        self.edited.setMaximumHeight(90)
        self.new_button = QPushButton("New")
        self.save_button = QPushButton("Save")
        form = QFormLayout()
        form.addRow("Title", self.title)
        form.addRow("Status", self.status)
        form.addRow("Description", self.description)
        form.addRow("Items", self.items)
        buttons = QHBoxLayout()
        buttons.addWidget(self.use_for_edits, 1)
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.save_button)
        lay = QVBoxLayout(self)
        lay.addWidget(self.table, 2)
        lay.addWidget(self.heading)
        lay.addLayout(form)
        lay.addLayout(buttons)
        lay.addWidget(QLabel("Edited under this change request"))
        lay.addWidget(self.edited)
        self.table.selectionModel().currentRowChanged.connect(self._on_row)
        self.new_button.clicked.connect(self._new_from_form)
        self.save_button.clicked.connect(self.save)
        self.use_for_edits.toggled.connect(self._toggle_edits)
        session.loaded.connect(self.refresh)
        session.item_changed.connect(lambda _u: self._refresh_edited())

    # data ###################################################################
    def refresh(self) -> None:
        if self.session.cfg is None:
            return
        statuses = list(self.session.cfg.changes.statuses)
        if [self.status.itemText(i) for i in range(self.status.count())] != statuses:
            self.status.clear()
            self.status.addItems(statuses)
        try:
            found = self.session.change_requests()
        except Exception as exc:  # noqa: BLE001 - unreadable change request files are reported by validate
            self.message.emit("error", f"Change requests could not be read: {exc}")
            return
        rows = [[c.id, c.status, c.title, c.raised_by, ", ".join(c.items)] for c in found]
        prov = Provenance.now(self.session.cfg, user=self.session.user)
        self._refreshing = True  # re-selecting the row below must not reload (and so overwrite) the form
        try:
            self.model.set_matrix(
                MatrixTable(
                    "Change requests", ["ID", "Status", "Title", "Raised by", "Items"], rows, [None] * len(rows), prov
                )
            )
            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setStretchLastSection(True)
            row = self._row_of(self.current_id) if self.current_id else -1
            if row >= 0:
                self.table.selectRow(row)
        finally:
            self._refreshing = False
        if self.current_id and row >= 0 and not self._form_dirty():
            self._load(self.current_id)

    def _row_of(self, cr_id: str) -> int:
        return next((r for r in range(self.model.rowCount()) if self.model.index(r, 0).data() == cr_id), -1)

    def select(self, cr_id: str) -> None:
        row = self._row_of(cr_id)
        if row >= 0:
            self.table.selectRow(row)
            self._load(cr_id)

    def _form_values(self) -> tuple[str, str, str, str]:
        return (self.title.text(), self.status.currentText(), self.description.toPlainText(), self.items.text())

    def _form_dirty(self) -> bool:
        return self._form_values() != self._snapshot

    def _on_row(self, current: object, _previous: object) -> None:
        if self._refreshing:
            return
        idx = self.table.currentIndex()
        if idx.isValid():
            self._load(str(self.model.index(idx.row(), 0).data()))

    def _load(self, cr_id: str) -> None:
        cr = self.session.change_request(cr_id)
        if cr is None:
            return
        self.current_id = cr_id
        self.heading.setText(f"{cr.id} — raised by {cr.raised_by}")
        self.title.setText(cr.title)
        self.status.setCurrentText(cr.status)
        self.description.setPlainText(cr.description)
        self.items.setText(", ".join(cr.items))
        self._snapshot = self._form_values()
        self.use_for_edits.blockSignals(True)
        self.use_for_edits.setChecked(self.session.active_cr == cr_id)
        self.use_for_edits.blockSignals(False)
        self._refresh_edited()

    def _refresh_edited(self) -> None:
        self.edited.clear()
        if self.current_id and self.session.cfg is not None:
            try:
                uids = self.session.store().edited_items(self.current_id)
            except (OSError, ValueError):  # unreadable history: the list is cosmetic
                uids = []
            for uid in uids:
                self.edited.addItem(uid)
            for i in range(self.edited.count()):
                it = self.edited.item(i)
                found = self.session.item(it.text())
                it.setText(f"{it.text()}  {found.attrs.get('title', '') if found else ''}".strip())

    # actions ##################################################################
    def create_request(self, title: str, description: str, items: list[str]) -> str | None:
        try:
            cr = self.session.store().create(title, description, self.session.user or _user(self.session), items)
        except ChangeRequestError as exc:
            self.message.emit("error", str(exc))
            return None
        self.current_id = cr.id
        self.refresh()
        self.message.emit("success", f"Created {cr.id}.")
        return cr.id

    def _new_from_form(self) -> None:
        self.create_request(self.title.text(), self.description.toPlainText(), _ids(self.items.text()))

    def save(self) -> None:
        if not self.current_id:
            self.message.emit("info", "Select a change request first.")
            return
        store = self.session.store()
        who = self.session.user or _user(self.session)
        try:
            cr = store.update(
                self.current_id,
                title=self.title.text(),
                description=self.description.toPlainText(),
                items=_ids(self.items.text()),
                who=who,
            )
            if self.status.currentText() != cr.status:
                store.set_status(cr.id, self.status.currentText(), who, "")
        except ChangeRequestError as exc:
            self.message.emit("error", str(exc))
            return
        self.refresh()
        self.message.emit("success", f"Saved {self.current_id}.")

    def _toggle_edits(self, on: bool) -> None:
        try:
            self.session.set_active_cr(self.current_id if on and self.current_id else None)
        except ValueError as exc:
            self.message.emit("error", str(exc))
            self.use_for_edits.blockSignals(True)
            self.use_for_edits.setChecked(False)
            self.use_for_edits.blockSignals(False)
            self.session.set_active_cr(None)
        _ = Qt


def _user(session: ProjectSession) -> str:
    from rvs_core.authoring import EditService

    assert session.root is not None
    return EditService(session.root).user

"""Export dialog: what to export, in which format, and where."""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rvs_core.exporters.export_request import ExportRequest, available_formats
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import named, secondary

HELP = {
    "vcm": "The verification control matrix lists every requirement with how, where and whether it is verified.",
    "trace": "The traceability matrix shows which items of one document are covered by items of another.",
    "coverage": "A summary of how many requirements of each document are traced and verified.",
    "impact": "Everything that a change to the item selected in the editor would affect.",
    "items": "All items as a table. You can edit it and import it again with File > Import Items.",
    "spec": "The requirements as a readable specification document.",
    "reqif": "A ReqIF file for exchanging requirements with other requirements tools.",
}
KINDS = {
    "vcm": "Verification control matrix",
    "trace": "Traceability matrix",
    "coverage": "Coverage by document",
    "impact": "Impact of the selected item",
    "items": "Items table (re-importable)",
    "spec": "Specification document",
    "reqif": "ReqIF exchange file (items, hierarchy, links)",
}


class ExportDialog(QDialog):
    def __init__(self, session: ProjectSession, parent: QWidget | None = None, current_uid: str = "") -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.setWindowTitle("Export")
        self.setMinimumSize(520, 340)
        self.current_uid = current_uid
        prefixes = [d.prefix for d in session.cfg.project.documents]
        self.kind = named(QComboBox(), "Content to export")
        for key, label in KINDS.items():
            self.kind.addItem(label, key)
        self.format = named(QComboBox(), "File format")
        self.document = named(QComboBox(), "Document")
        self.document.addItems(["All documents", *prefixes])
        self.trace_source = named(QComboBox(), "From document")
        self.trace_target = named(QComboBox(), "To document")
        self.trace_source.addItems(prefixes)
        self.trace_target.addItems(prefixes)
        self.trace_target.setCurrentIndex(1 if len(prefixes) > 1 else 0)
        self.trace_direction = named(QComboBox(), "Direction")
        self.trace_direction.addItems(["down", "up"])
        self.path = named(QLineEdit(), "Export file path")
        self.path.setPlaceholderText("Where to save the file")
        browse = QPushButton("Browse…")
        secondary(browse)
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)
        self.form = QFormLayout()
        self.form.addRow("Content", self.kind)
        self.form.addRow("Format", self.format)
        self.form.addRow("Document", self.document)
        self.form.addRow("From", self.trace_source)
        self.form.addRow("To", self.trace_target)
        self.form.addRow("Direction", self.trace_direction)
        self.form.addRow("Save as", path_row)
        self.help = QLabel()
        self.help.setWordWrap(True)
        self.help.setObjectName("Empty")
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setAccessibleName("Problem")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Export")
        secondary(buttons.button(QDialogButtonBox.StandardButton.Cancel))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.help)
        lay.addLayout(self.form)
        lay.addWidget(self.problem)
        lay.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self._on_kind)
        self.path.textChanged.connect(self._update)
        self._on_kind()

    def set_kind(self, key: str) -> None:
        self.kind.setCurrentIndex(self.kind.findData(key))

    def _key(self) -> str:
        return str(self.kind.currentData())

    def _on_kind(self, *_a: object) -> None:
        key = self._key()
        self.help.setText(HELP.get(key, ""))
        current = self.format.currentText()
        self.format.clear()
        self.format.addItems(available_formats(key))
        if current in available_formats(key):
            self.format.setCurrentText(current)
        shown = {
            self.document: key in ("vcm", "spec", "reqif"),
            self.trace_source: key == "trace",
            self.trace_target: key == "trace",
            self.trace_direction: key == "trace",
        }
        for widget, visible in shown.items():
            widget.setVisible(visible)
            label = self.form.labelForField(widget)
            if label is not None:
                label.setVisible(visible)
        self._update()

    def validate(self) -> str:
        text = self.path.text().strip()
        if not text:
            return "Choose where to save the file (Browse… or type a path)."
        folder = Path(text).parent
        if not folder.is_dir():
            return f"The folder {folder} does not exist. Choose an existing folder."
        if Path(text).is_dir():
            return "That is a folder. Type a file name as well."
        return ""

    def _update(self, *_a: object) -> None:
        text = self.validate()
        self.problem.setText(text)
        self.ok_button.setEnabled(not text)

    def accept(self) -> None:
        self._update()
        if self.validate():
            self.path.setFocus()
            return
        super().accept()

    def request(self) -> ExportRequest:
        key = self._key()
        docs = () if self.document.currentIndex() <= 0 else (self.document.currentText(),)
        trace = (self.trace_source.currentText(), self.trace_target.currentText(), self.trace_direction.currentText())
        return ExportRequest(
            key,
            self.format.currentText(),
            documents=docs if key in ("vcm", "spec", "reqif") else (),
            trace=trace if key == "trace" else ("", "", "down"),
            impact_uid=self.current_uid if key == "impact" else "",
        )

    def destination(self) -> Path:
        path = Path(self.path.text().strip())
        suffix = "." + self.format.currentText()
        return path if path.suffix.lower() == suffix else path.with_name(path.name + suffix)

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getSaveFileName(self, "Save export as", self.path.text())
        if chosen:
            self.path.setText(chosen)

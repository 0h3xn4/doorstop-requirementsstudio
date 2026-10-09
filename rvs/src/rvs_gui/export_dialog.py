"""Export dialog: what to export, in which format, and where."""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rvs_core.exporters.export_request import ExportRequest, available_formats
from rvs_gui.session import ProjectSession

KINDS = {
    "vcm": "Verification control matrix",
    "trace": "Traceability matrix",
    "coverage": "Coverage by document",
    "impact": "Impact of the selected item",
    "items": "Items table (re-importable)",
    "spec": "Specification document",
}


class ExportDialog(QDialog):
    def __init__(self, session: ProjectSession, parent: QWidget | None = None, current_uid: str = "") -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.setWindowTitle("Export")
        self.current_uid = current_uid
        prefixes = [d.prefix for d in session.cfg.project.documents]
        self.kind = QComboBox()
        for key, label in KINDS.items():
            self.kind.addItem(label, key)
        self.format = QComboBox()
        self.document = QComboBox()
        self.document.addItems(["All documents", *prefixes])
        self.trace_source, self.trace_target = QComboBox(), QComboBox()
        self.trace_source.addItems(prefixes)
        self.trace_target.addItems(prefixes)
        self.trace_target.setCurrentIndex(1 if len(prefixes) > 1 else 0)
        self.trace_direction = QComboBox()
        self.trace_direction.addItems(["down", "up"])
        self.path = QLineEdit()
        browse = QPushButton("Browse…")
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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(self.form)
        lay.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self._on_kind)
        self._on_kind()

    def set_kind(self, key: str) -> None:
        self.kind.setCurrentIndex(self.kind.findData(key))

    def _key(self) -> str:
        return str(self.kind.currentData())

    def _on_kind(self, *_a: object) -> None:
        key = self._key()
        current = self.format.currentText()
        self.format.clear()
        self.format.addItems(available_formats(key))
        if current in available_formats(key):
            self.format.setCurrentText(current)
        shown = {
            self.document: key in ("vcm", "spec"),
            self.trace_source: key == "trace",
            self.trace_target: key == "trace",
            self.trace_direction: key == "trace",
        }
        for widget, visible in shown.items():
            widget.setVisible(visible)
            label = self.form.labelForField(widget)
            if label is not None:
                label.setVisible(visible)

    def request(self) -> ExportRequest:
        key = self._key()
        docs = () if self.document.currentIndex() <= 0 else (self.document.currentText(),)
        trace = (self.trace_source.currentText(), self.trace_target.currentText(), self.trace_direction.currentText())
        return ExportRequest(
            key,
            self.format.currentText(),
            documents=docs if key in ("vcm", "spec") else (),
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

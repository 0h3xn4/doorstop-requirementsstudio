"""Dialog for creating a new project from a template."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
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

from rvs_core.project_templates import TEMPLATES


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New project")
        self.resize(520, 260)
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("A new, empty folder (it is created if needed)")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Project name")
        self.template = QComboBox()
        for key, template in TEMPLATES.items():
            self.template.addItem(template.title, key)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.git = QCheckBox("Keep this project under Git version control (needed for baselines)")
        self.git.setChecked(True)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form = QFormLayout()
        form.addRow("Folder", row)
        form.addRow("Name", self.name)
        form.addRow("Template", self.template)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.description)
        lay.addWidget(self.git)
        lay.addStretch(1)
        lay.addWidget(buttons)
        self.template.currentIndexChanged.connect(self._on_template)
        self._on_template()

    def _on_template(self) -> None:
        template = TEMPLATES[self.template.currentData()]
        self.description.setText(template.description)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Project folder")
        if chosen:
            self.folder.setText(chosen)

    def values(self) -> tuple[Path, str, str, bool]:
        return (
            Path(self.folder.text().strip()),
            self.name.text().strip(),
            self.template.currentData(),
            self.git.isChecked(),
        )

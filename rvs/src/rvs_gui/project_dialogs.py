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
from rvs_gui.widgets import named, secondary


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New project")
        self.resize(560, 320)
        self.setMinimumWidth(480)
        self.folder = named(QLineEdit(), "Project folder")
        self.folder.setPlaceholderText("A new, empty folder (it is created if needed)")
        browse = QPushButton("Browse…")
        secondary(browse)
        browse.clicked.connect(self._browse)
        self.name = named(QLineEdit(), "Project name")
        self.name.setPlaceholderText("Project name")
        self.template = named(QComboBox(), "Template")
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
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setAccessibleName("Problem")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Create project")
        secondary(buttons.button(QDialogButtonBox.StandardButton.Cancel))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.description)
        lay.addWidget(self.git)
        lay.addStretch(1)
        lay.addWidget(self.problem)
        lay.addWidget(buttons)
        self.template.currentIndexChanged.connect(self._on_template)
        self.folder.textChanged.connect(self._update)
        self.name.textChanged.connect(self._update)
        self._on_template()
        self._update()

    def validate(self) -> str:
        """What is wrong with the answers, in a sentence; empty when the project can be created."""
        folder = self.folder.text().strip()
        if not folder:
            return "Choose a folder for the project (Browse… or type a path)."
        if not self.name.text().strip():
            return "Give the project a name."
        path = Path(folder)
        if path.exists() and not path.is_dir():
            return f"{path} is a file, not a folder. Choose a folder."
        if path.is_dir() and any(path.iterdir()):
            return "That folder is not empty. Choose a new or empty folder."
        return ""

    def _update(self, *_a: object) -> None:
        text = self.validate()
        self.problem.setText(text)
        self.ok_button.setEnabled(not text)

    def accept(self) -> None:
        self._update()
        if self.validate():
            return  # stay open; the message above the buttons says what to fix
        super().accept()

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

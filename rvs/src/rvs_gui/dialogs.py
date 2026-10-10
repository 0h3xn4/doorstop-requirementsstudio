"""Small dialogs."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from rvs_gui.session import ProjectSession
from rvs_gui.widgets import named, secondary


class NewItemDialog(QDialog):
    """Ask for document, title and parents of a new requirement (or the requirements a verification item verifies).

    The OK button stays disabled until the answers are usable, and says what is missing; the dialog never closes on
    a mistake."""

    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        document: str | None = None,
        kind: str = "requirements",
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.session = session
        self.setWindowTitle("New requirement" if kind == "requirements" else "New verification item")
        self.setMinimumSize(480, 260)
        assert session.cfg is not None
        self._parent_of = {d.prefix: d.parent for d in session.cfg.project.documents}
        self.document = named(QComboBox(), "Document")
        self.document.addItems(session.documents_of_kind(kind))
        if document and document in session.documents_of_kind(kind):
            self.document.setCurrentText(document)
        self.title = named(QLineEdit(), "Title")
        self.title.setPlaceholderText("Short title")
        self.parents = named(QLineEdit(), "Verifies" if kind == "verification" else "Parents")
        verification = kind == "verification"
        self.parents.setPlaceholderText(
            "IDs of the requirements it verifies, comma separated"
            if verification
            else "Parent item IDs, comma separated"
        )
        self.help = QLabel(
            "A verification item describes how one or more requirements will be shown to be met. "
            "Enter the IDs of those requirements, separated by commas."
            if verification
            else "Choose the document and give the requirement a short title. A requirement in a lower-level "
            "document derives from requirements of the document above it: enter their IDs, separated by commas. "
            "You write the statement itself afterwards in the editor."
        )
        self.help.setWordWrap(True)
        self.help.setObjectName("Empty")
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setAccessibleName("Problem")
        form = QFormLayout()
        form.addRow("Document", self.document)
        form.addRow("Title", self.title)
        form.addRow("Verifies" if verification else "Parents", self.parents)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Create verification item" if verification else "Create requirement")
        secondary(self.buttons.button(QDialogButtonBox.StandardButton.Cancel))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.help)
        lay.addLayout(form)
        lay.addWidget(self.problem)
        lay.addWidget(self.buttons)
        self.document.currentTextChanged.connect(self._on_document)
        self.title.textChanged.connect(self._update)
        self.parents.textChanged.connect(self._update)
        self._on_document(self.document.currentText())

    def _on_document(self, prefix: str) -> None:
        root = self.kind == "requirements" and self._parent_of.get(prefix) is None
        self.parents.setEnabled(not root)
        if root:
            self.parents.clear()
        self._update()

    def documents(self) -> list[str]:
        return [self.document.itemText(i) for i in range(self.document.count())]

    def values(self) -> tuple[str, str, list[str]]:
        parents = [p.strip() for p in self.parents.text().split(",") if p.strip()]
        return self.document.currentText(), self.title.text().strip(), parents

    def validate(self) -> str:
        """What is wrong with the answers, in a sentence; empty when they are usable."""
        document, title, parents = self.values()
        if not document:
            return "This project has no document to create the item in."
        if not title:
            return "Give the item a short title."
        unknown = [p for p in parents if self.session.item(p) is None]
        if unknown:
            return f"There is no item {', '.join(unknown)} in this project. Check the IDs."
        if self.kind == "verification" and not parents:
            return "Enter the ID of at least one requirement that this item verifies."
        return ""

    def _update(self, *_a: object) -> None:
        text = self.validate()
        self.problem.setText(text)
        self.ok_button.setEnabled(not text)

    def accept(self) -> None:
        self._update()
        if self.validate():
            self.title.setFocus() if not self.title.text().strip() else self.parents.setFocus()
            return  # stay open: the message above the buttons says what to fix
        super().accept()

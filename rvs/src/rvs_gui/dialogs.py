"""Small dialogs."""

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout, QWidget

from rvs_gui.session import ProjectSession


class NewItemDialog(QDialog):
    """Ask for document, title and parents of a new requirement."""

    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        document: str | None = None,
        kind: str = "requirements",
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle("New requirement" if kind == "requirements" else "New verification item")
        assert session.cfg is not None
        self._parent_of = {d.prefix: d.parent for d in session.cfg.project.documents}
        self.document = QComboBox()
        self.document.addItems(session.documents_of_kind(kind))
        if document and document in session.documents_of_kind(kind):
            self.document.setCurrentText(document)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Short title")
        self.parents = QLineEdit()
        verification = kind == "verification"
        self.parents.setPlaceholderText(
            "IDs of the requirements it verifies, comma separated"
            if verification
            else "Parent item IDs, comma separated"
        )
        form = QFormLayout()
        form.addRow("Document", self.document)
        form.addRow("Title", self.title)
        form.addRow("Verifies" if verification else "Parents", self.parents)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)
        self.document.currentTextChanged.connect(self._on_document)
        self._on_document(self.document.currentText())

    def _on_document(self, prefix: str) -> None:
        root = self.kind == "requirements" and self._parent_of.get(prefix) is None
        self.parents.setEnabled(not root)
        if root:
            self.parents.clear()

    def documents(self) -> list[str]:
        return [self.document.itemText(i) for i in range(self.document.count())]

    def values(self) -> tuple[str, str, list[str]]:
        parents = [p.strip() for p in self.parents.text().split(",") if p.strip()]
        return self.document.currentText(), self.title.text().strip(), parents

"""Edit the project's glossary: acronyms and terms. Saving rewrites config/glossary.yaml and re-checks the project."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rvs_core.glossary import save_glossary
from rvs_gui.session import ProjectSession


def _table(headers: tuple[str, str]) -> QTableWidget:
    table = QTableWidget(0, 2)
    table.setHorizontalHeaderLabels(list(headers))
    table.horizontalHeader().setStretchLastSection(True)
    table.setColumnWidth(0, 180)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    return table


class GlossaryDialog(QDialog):
    def __init__(self, session: ProjectSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.session = session
        self.setWindowTitle("Glossary and acronyms")
        self.resize(640, 480)
        self.message = QLabel("")
        self.acronyms = _table(("Acronym", "Expansion"))
        self.terms = _table(("Term", "Definition"))
        for acronym, expansion in sorted(session.cfg.glossary.acronyms.items()):
            self._append(self.acronyms, acronym, expansion)
        for term, definition in sorted(session.cfg.glossary.terms):
            self._append(self.terms, term, definition)
        tabs = QTabWidget()
        tabs.addTab(self._with_buttons(self.acronyms, "acronym"), "Acronyms")
        tabs.addTab(self._with_buttons(self.terms, "term"), "Terms")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Acronyms listed here are not reported as undefined in requirement statements."))
        lay.addWidget(tabs, 1)
        lay.addWidget(self.message)
        lay.addWidget(buttons)

    def _with_buttons(self, table: QTableWidget, what: str) -> QWidget:
        add = QPushButton(f"Add {what}")
        remove = QPushButton("Remove selected")
        add.clicked.connect(lambda: self._append(table, "", ""))
        remove.clicked.connect(lambda: self._remove_selected(table))
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.addWidget(table, 1)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        lay.addLayout(row)
        return holder

    @staticmethod
    def _remove_selected(table: QTableWidget) -> None:
        for row in sorted({i.row() for i in table.selectedIndexes()}, reverse=True):
            table.removeRow(row)

    @staticmethod
    def _append(table: QTableWidget, first: str, second: str) -> None:
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(first))
        table.setItem(row, 1, QTableWidgetItem(second))

    @staticmethod
    def _texts(table: QTableWidget) -> list[tuple[str, str]]:
        out = []
        for row in range(table.rowCount()):
            a, b = table.item(row, 0), table.item(row, 1)
            out.append(((a.text() if a else "").strip(), (b.text() if b else "").strip()))
        return out

    def _say(self, text: str) -> bool:
        self.message.setText(text)
        return False

    def add_acronym(self, acronym: str, expansion: str) -> bool:
        acronym, expansion = acronym.strip(), expansion.strip()
        if not acronym or not expansion:
            return self._say("An acronym needs both the short form and its expansion.")
        if len(acronym) < 2:
            return self._say(f"'{acronym}' is too short: an acronym has at least two characters.")
        if any(a == acronym for a, _e in self._texts(self.acronyms)):
            return self._say(f"{acronym} is already in the list.")
        self._append(self.acronyms, acronym, expansion)
        self.message.setText("")
        return True

    def add_term(self, term: str, definition: str) -> bool:
        term, definition = term.strip(), definition.strip()
        if not term or not definition:
            return self._say("A term needs both the word and its definition.")
        if any(t.lower() == term.lower() for t, _d in self._texts(self.terms)):
            return self._say(f"'{term}' is already defined.")
        self._append(self.terms, term, definition)
        self.message.setText("")
        return True

    def entries(self) -> tuple[list[tuple[str, str]], dict[str, str]]:
        terms = [(t, d) for t, d in self._texts(self.terms) if t and d]
        acronyms = {a: e for a, e in self._texts(self.acronyms) if len(a) >= 2 and e}
        return terms, acronyms

    def save(self) -> bool:
        assert self.session.root is not None
        terms, acronyms = self.entries()
        try:
            save_glossary(self.session.root, terms, acronyms)
        except OSError as exc:
            self._say(f"The glossary could not be saved ({exc.strerror or exc}). Nothing was changed.")
            return False
        self.session.refresh()
        return True

    def _accept(self) -> None:
        if self.save():
            self.accept()


_ = Qt

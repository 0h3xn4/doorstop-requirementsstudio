"""Edit the project's glossary: acronyms and terms. Saving rewrites config/glossary.yaml and re-checks the project."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rvs_core.glossary import save_glossary
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import keyboard_view, named, secondary


def _table(headers: tuple[str, str], name: str) -> QTableWidget:
    table = named(keyboard_view(QTableWidget(0, 2)), name)
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
        self.message.setWordWrap(True)
        self.message.setAccessibleName("Problems in the glossary")
        self.acronyms = _table(("Acronym", "Expansion"), "Acronyms")
        self.terms = _table(("Term", "Definition"), "Terms")
        self.new_acronym = named(QLineEdit(), "New acronym")
        self.new_expansion = named(QLineEdit(), "Expansion of the new acronym")
        self.new_term = named(QLineEdit(), "New term")
        self.new_definition = named(QLineEdit(), "Definition of the new term")
        for acronym, expansion in sorted(session.cfg.glossary.acronyms.items()):
            self._append(self.acronyms, acronym, expansion)
        for term, definition in sorted(session.cfg.glossary.terms):
            self._append(self.terms, term, definition)
        tabs = QTabWidget()
        tabs.addTab(self._with_buttons(self.acronyms, "acronym", self.new_acronym, self.new_expansion), "Acronyms")
        tabs.addTab(self._with_buttons(self.terms, "term", self.new_term, self.new_definition), "Terms")
        self.tabs = tabs
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        secondary(buttons.button(QDialogButtonBox.StandardButton.Cancel))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Acronyms listed here are not reported as undefined in requirement statements."))
        lay.addWidget(tabs, 1)
        lay.addWidget(self.message)
        lay.addWidget(buttons)

    def _with_buttons(self, table: QTableWidget, what: str, first: QLineEdit, second: QLineEdit) -> QWidget:
        """The table, a row to type a new entry in (checked before it is added), and a button to remove rows."""
        first.setPlaceholderText(table.horizontalHeaderItem(0).text())  # type: ignore[union-attr]
        second.setPlaceholderText(table.horizontalHeaderItem(1).text())  # type: ignore[union-attr]
        add = QPushButton(f"Add {what}")
        remove = QPushButton("Remove selected")
        secondary(remove)
        adder = self.add_acronym if what == "acronym" else self.add_term

        def add_clicked() -> None:
            if adder(first.text(), second.text()):  # same checks as every other way in
                first.clear()
                second.clear()
                first.setFocus()

        add.clicked.connect(add_clicked)
        first.returnPressed.connect(add_clicked)
        second.returnPressed.connect(add_clicked)
        remove.clicked.connect(lambda: self._remove_selected(table))
        holder = QWidget()
        lay = QVBoxLayout(holder)
        entry = QHBoxLayout()
        entry.addWidget(first, 1)
        entry.addWidget(second, 2)
        entry.addWidget(add)
        lay.addLayout(entry)
        lay.addWidget(table, 1)
        row = QHBoxLayout()
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

    def problems(self) -> list[tuple[QTableWidget, int, str]]:
        """Every row that cannot be saved, with a sentence saying why. Rows left completely empty are ignored."""
        out: list[tuple[QTableWidget, int, str]] = []
        for table, label, first_name, second_name, min_length in (
            (self.acronyms, "Acronyms", "acronym", "expansion", 2),
            (self.terms, "Terms", "term", "definition", 1),
        ):
            seen: set[str] = set()
            for row, (a, b) in enumerate(self._texts(table)):
                if not a and not b:
                    continue
                where = f"{label}, row {row + 1}"
                if not a:
                    out.append((table, row, f"{where}: the {first_name} is missing."))
                elif len(a) < min_length:
                    out.append(
                        (
                            table,
                            row,
                            f"{where}: '{a}' is too short, an {first_name} has at least {min_length} characters.",
                        )
                    )
                elif not b:
                    out.append((table, row, f"{where}: '{a}' needs a {second_name}."))
                elif a.lower() in seen:
                    out.append((table, row, f"{where}: '{a}' appears more than once."))
                seen.add(a.lower())
        return out

    def save(self) -> bool:
        assert self.session.root is not None
        bad = self.problems()
        if bad:  # say which rows are wrong; saving would silently drop them
            table, row, _text = bad[0]
            self.tabs.setCurrentIndex(0 if table is self.acronyms else 1)
            table.setCurrentCell(row, 0)
            table.setFocus()
            return self._say("Nothing was saved. Fix these rows first: " + " ".join(t for _tb, _r, t in bad))
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

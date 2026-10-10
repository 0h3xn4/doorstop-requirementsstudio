"""Autocomplete from the project's own data only (spec rule 5): item IDs in list fields, values already in use."""

from collections.abc import Callable, Iterable

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QLineEdit, QWidget


class UidLineEdit(QLineEdit):
    """A comma-separated list of item IDs that completes the token being typed."""

    def __init__(self, candidates: Callable[[], Iterable[str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._candidates = candidates
        self._model = QStringListModel(self)
        completer = QCompleter(self._model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
        self.textEdited.connect(self._refresh)

    def suggestions(self, text: str) -> list[str]:
        head, sep, last = text.rpartition(",")
        taken = [t.strip() for t in head.split(",") if t.strip()]
        prefix = last.strip()
        pool = sorted(set(self._candidates()))
        if prefix and prefix in pool:
            return []  # the token is already a complete ID
        matches = [u for u in pool if u not in taken and u.upper().startswith(prefix.upper())]
        lead = ", ".join(taken)
        return [f"{lead}, {u}" if lead else u for u in matches]

    def _refresh(self, text: str) -> None:
        self._model.setStringList(self.suggestions(text))


def value_completer(values: Iterable[str], parent: QWidget) -> QCompleter:
    completer = QCompleter(sorted({v for v in values if v}), parent)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    return completer

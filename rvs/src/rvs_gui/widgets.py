"""Small Carbon-style building blocks: inline notification, acronym highlighting and accessibility helpers."""

import contextlib
from typing import TypeVar

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAccessible, QAccessibleEvent, QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QStyle,
    QToolButton,
    QWidget,
)

from rvs_core.glossary import find_acronyms
from rvs_gui.theme import TOKENS

W = TypeVar("W", bound=QWidget)
V = TypeVar("V", bound=QAbstractItemView)
T = TypeVar("T", bound=QPlainTextEdit)

_KIND_TOKEN = {"error": "support_error", "warning": "support_warning", "success": "support_success", "info": "link"}
#: The word that names a severity: colour is never the only cue (accessibility), and screen readers read it.
KIND_WORD = {"error": "Error", "warning": "Warning", "success": "Success", "info": "Information"}
_KIND_ICON = {
    "error": QStyle.StandardPixmap.SP_MessageBoxCritical,
    "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "success": QStyle.StandardPixmap.SP_DialogApplyButton,
    "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
}


def named(widget: W, accessible_name: str, description: str = "") -> W:
    """Give ``widget`` the name a screen reader announces (and an optional longer description)."""
    widget.setAccessibleName(accessible_name)
    if description:
        widget.setAccessibleDescription(description)
    return widget


def secondary(button: QAbstractButton) -> QAbstractButton:
    """Style ``button`` as a secondary action (Cancel, Discard, Revert): outlined instead of solid blue."""
    button.setProperty("variant", "secondary")
    return button


def keyboard_view(view: V) -> V:
    """A table or tree that Tab leaves (Tab inside a table is a keyboard trap: arrows move between cells instead)."""
    view.setTabKeyNavigation(False)
    return view


def keyboard_text(edit: T) -> T:
    """A multi-line field in which Tab moves on to the next field (it does not insert a tab character)."""
    edit.setTabChangesFocus(True)
    return edit


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    """'1 error', '2 errors'."""
    return f"{count} {singular if count == 1 else (plural_form or singular + 's')}"


def problem_counts(errors: int, warnings: int, info: int | None = None) -> str:
    """'1 error, 2 warnings' (and ', 3 info' when given): the one wording used by the status bar and the Problems panel."""
    text = f"{plural(errors, 'error')}, {plural(warnings, 'warning')}"
    return text if info is None else f"{text}, {info} info"


class InlineNotification(QFrame):
    """Carbon inline notification: coloured left bar, severity icon and word, message, close button. Hidden until used."""

    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.kind = "info"
        self.setObjectName("InlineNotification")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        self._icon = QLabel()
        self._icon.setFixedSize(20, 20)
        self._icon.setStyleSheet("background: transparent;")
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setMinimumWidth(120)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setStyleSheet("background: transparent;")
        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("Dismiss this message (Esc)")
        self.close_button.setAccessibleName("Dismiss notification")
        self.close_button.clicked.connect(self.dismiss)
        lay.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._label, 1)
        lay.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.setAccessibleName("Notification")
        self.hide()

    def show_message(self, kind: str, text: str) -> None:
        self.kind = kind if kind in _KIND_TOKEN else "info"
        word = KIND_WORD[self.kind]
        self._label.setText(f"<b>{word}:</b> {_escape(text)}")
        self._label.setAccessibleName(f"{word}: {text}")
        self.setAccessibleName(f"{word}: {text}")
        self._raw = text
        self._icon.setPixmap(self.style().standardIcon(_KIND_ICON[self.kind]).pixmap(20, 20))
        self._apply_style()
        self.show()
        if self.kind in ("error", "warning"):
            with contextlib.suppress(Exception):  # best effort: never a reason to lose the message
                QAccessible.updateAccessibility(QAccessibleEvent(self, QAccessible.Event.Alert))

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"#InlineNotification {{ background: {TOKENS['layer']}; border-left: 4px solid {TOKENS[_KIND_TOKEN[self.kind]]}; }}"
        )

    def restyle(self) -> None:
        """Re-apply the colours of the current theme (the message itself is unchanged)."""
        self._apply_style()

    _raw = ""

    def text(self) -> str:
        """The message without its severity word."""
        return self._raw

    def display_text(self) -> str:
        """What is on screen: the severity word, then the message."""
        return f"{KIND_WORD[self.kind]}: {self._raw}"

    def dismiss(self) -> None:
        self.hide()
        self.closed.emit()


def _escape(text: str) -> str:
    import html

    return html.escape(text)


class AcronymHighlighter(QSyntaxHighlighter):
    """Underlines acronyms that are not in the glossary (same detection as the undefined-acronym rule)."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self.known: set[str] = set()
        self.min_length = 2
        self.ignore: set[str] = set()
        self._format = QTextCharFormat()
        self._format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        self._format.setUnderlineColor(QColor(TOKENS["support_error"]))

    def configure(self, known: set[str], min_length: int, ignore: set[str]) -> None:
        self.known, self.min_length, self.ignore = known, min_length, ignore
        self.rehighlight()

    def undefined_spans(self) -> list[tuple[int, int]]:
        text = self.document().toPlainText() if self.document() else ""
        return [
            (h.start, h.end)
            for h in find_acronyms(text, self.known, min_length=self.min_length, ignore=self.ignore)
            if not h.defined
        ]

    def highlightBlock(self, text: str) -> None:
        for hit in find_acronyms(text, self.known, min_length=self.min_length, ignore=self.ignore):
            if not hit.defined:
                self.setFormat(hit.start, hit.end - hit.start, self._format)

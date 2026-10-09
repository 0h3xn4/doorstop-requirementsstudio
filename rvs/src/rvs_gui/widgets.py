"""Small Carbon-style building blocks: inline notification and acronym highlighting."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from rvs_core.glossary import find_acronyms
from rvs_gui.theme import TOKENS

_KIND_COLOR = {
    "error": TOKENS["support_error"],
    "warning": TOKENS["support_warning"],
    "success": TOKENS["support_success"],
    "info": TOKENS["interactive"],
}


class InlineNotification(QFrame):
    """Carbon inline notification: coloured left bar, message, close button. Hidden until used."""

    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.kind = "info"
        self.setObjectName("InlineNotification")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setStyleSheet("background: transparent;")
        close = QToolButton()
        close.setText("×")
        close.clicked.connect(self.dismiss)
        lay.addWidget(self._label, 1)
        lay.addWidget(close)
        self.hide()

    def show_message(self, kind: str, text: str) -> None:
        self.kind = kind
        self._label.setText(text)
        self.setStyleSheet(
            f"#InlineNotification {{ background: {TOKENS['layer']}; border-left: 4px solid {_KIND_COLOR[kind]}; }}"
        )
        self.show()

    def text(self) -> str:
        return self._label.text()

    def dismiss(self) -> None:
        self.hide()
        self.closed.emit()


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

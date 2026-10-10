"""Form widgets for template attributes, shared by the editor and the new-requirement wizard.

One place decides which widget an attribute type gets, how its help text is shown, and how it autocompletes
(from the project's own data only)."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QLabel, QLineEdit, QPlainTextEdit, QWidget

from rvs_core.config.model import AttributeDef
from rvs_core.exporters.itemsio import join_string_list, split_string_list
from rvs_gui.completion import UidLineEdit
from rvs_gui.session import ProjectSession
from rvs_gui.theme import TOKENS
from rvs_gui.widgets import keyboard_text

LIST_TYPES = {"uid-list", "string-list"}
# Plain string attributes that complete from values already used in the project.
_NO_COMPLETION = {"title"}


def parse_list(text: str) -> list[str]:
    return [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]


def normalise(value: Any, kind: str) -> Any:
    """A stored value in the form the widgets compare: lists as lists, everything else as stripped text (YAML keeps a
    trailing newline on multi-line text, which ``get_value`` strips, so both sides must be stripped)."""
    if kind in LIST_TYPES:
        return [str(v) for v in value] if value else []
    return "" if value is None else str(value).strip()


#: What the user reads for attributes whose stored name is a code. The template's own label wins when it has one.
KNOWN_LABELS = {
    "v_status": "Verification status",
    "link_verifies": "Verifies",
    "link_satisfies": "Satisfies",
    "link_refines": "Refines",
    "link_conflicts": "Conflicts with",
    "link_conflicts_with": "Conflicts with",
    "nonconformances": "Non-conformances",
    "proc_id": "Procedure ID",
    "verify_method": "Verification method",
    "verify_level": "Verification level",
    "executed_on": "Executed on",
    "standard_clause": "Standard clause",
}
_ACRONYM_WORDS = {"id": "ID", "uid": "UID"}


def plain_label(adef: AttributeDef) -> str:
    """The attribute's name as a person reads it, without the required marker."""
    own = getattr(adef, "label", "")
    if own:
        return str(own)
    if adef.name in KNOWN_LABELS:
        return KNOWN_LABELS[adef.name]
    words = [_ACRONYM_WORDS.get(w, w) for w in adef.name.split("_")]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def label_text(adef: AttributeDef) -> str:
    return plain_label(adef) + (" *" if adef.required else "")


def help_text(adef: AttributeDef) -> str:
    return adef.help or ""


def help_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {TOKENS['text_secondary']}; font-size: 12px; margin-bottom: 4px;")
    return label


def make_widget(session: ProjectSession, adef: AttributeDef, on_change: Callable[..., None]) -> QWidget:
    """The input widget for ``adef``; its tooltip carries the attribute's help text."""
    assert session.cfg is not None
    widget: QWidget
    if adef.type == "enum" and adef.vocab:
        combo = QComboBox()
        if not adef.required:
            combo.addItem("")
        combo.addItems(session.cfg.vocab.values(adef.vocab))
        combo.currentTextChanged.connect(on_change)
        widget = combo
    elif adef.type == "text":
        box = QPlainTextEdit()
        keyboard_text(box)
        box.setMaximumHeight(70)
        box.textChanged.connect(on_change)
        widget = box
    elif adef.type == "uid-list":
        edit = UidLineEdit(lambda: [i.uid for i in session.items])
        edit.setPlaceholderText("item IDs, comma separated")
        edit.textChanged.connect(on_change)
        widget = edit
    else:
        line = QLineEdit()
        if adef.type == "date":
            line.setPlaceholderText("YYYY-MM-DD")
        if adef.type == "string-list":
            line.setPlaceholderText("comma separated")
        if adef.type == "string" and adef.name not in _NO_COMPLETION:
            completer = QCompleter(QStringListModel(line), line)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            line.setCompleter(completer)
        line.textChanged.connect(on_change)
        widget = line
    widget.setAccessibleName(plain_label(adef))
    tip = help_text(adef)
    widget.setToolTip((tip + "\n\nRequired." if adef.required else tip) if tip else "")
    widget.setMinimumHeight(56 if isinstance(widget, QPlainTextEdit) else 28)
    return widget


def refresh_completions(session: ProjectSession, defs: list[AttributeDef], widgets: dict[str, QWidget]) -> None:
    """Refill the value completers of string fields with what the project already uses."""
    for adef in defs:
        widget = widgets.get(adef.name)
        if isinstance(widget, QLineEdit) and adef.type == "string" and widget.completer() is not None:
            values = {str(i.attrs.get(adef.name)) for i in session.items if i.attrs.get(adef.name)}
            model = widget.completer().model()
            if isinstance(model, QStringListModel):
                model.setStringList(sorted(values))


def get_value(widget: QWidget, kind: str) -> Any:
    if isinstance(widget, QComboBox):
        return widget.currentText()
    raw = widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()  # type: ignore[attr-defined]
    raw = raw.strip()
    if kind == "string-list":
        return split_string_list(raw)  # an entry may contain a comma (written \,): lossless
    return parse_list(raw) if kind in LIST_TYPES else raw


def set_value(widget: QWidget, value: Any, kind: str = "") -> None:
    if isinstance(value, list):
        text = join_string_list(value) if kind == "string-list" else ", ".join(str(v) for v in value)
    else:
        text = "" if value is None else str(value)
    if isinstance(widget, QComboBox):
        widget.setCurrentIndex(max(0, widget.findText(text)))
    elif isinstance(widget, QPlainTextEdit):
        widget.setPlainText(text)
    else:
        widget.setText(text)  # type: ignore[attr-defined]

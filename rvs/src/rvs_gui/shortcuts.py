"""Keyboard shortcuts: one table (action id -> default key, description); user overrides come from the user config."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTableView, QVBoxLayout, QWidget

from rvs_core import userconfig
from rvs_gui.widgets import keyboard_view, named

SHORTCUTS: dict[str, tuple[str, str]] = {
    "open_project": ("Ctrl+O", "Open a project folder"),
    "new_project": ("Ctrl+Alt+N", "Create a new project from a template"),
    "import_items": ("Ctrl+I", "Import items from CSV or XLSX"),
    "export": ("Ctrl+E", "Export a matrix, specification or items table"),
    "quit": ("Ctrl+Q", "Quit"),
    "new_requirement": ("Ctrl+N", "New requirement (wizard in guided mode, quick dialog in expert mode)"),
    "new_verification": ("Ctrl+Shift+N", "New verification item"),
    "save": ("Ctrl+S", "Save the item being edited"),
    "revert": ("Ctrl+R", "Revert the item being edited"),
    "find": ("Ctrl+F", "Search items (focus the search field)"),
    "go_to": ("Ctrl+G", "Go to an item by ID"),
    "next_problem": ("F8", "Jump to the next problem"),
    "prev_problem": ("Shift+F8", "Jump to the previous problem"),
    "focus_problems": ("F6", "Move the focus to the Problems panel"),
    "focus_editor": ("F4", "Move the focus to the requirement editor (Enter on an item row does the same)"),
    "refresh": ("F5", "Reload and re-check the project"),
    "full_validation": ("Ctrl+Shift+V", "Run Doorstop's full validation"),
    "new_baseline": ("Ctrl+Shift+B", "Create a baseline"),
    "glossary": ("Ctrl+Shift+G", "Edit the glossary and acronym list"),
    "toggle_mode": ("Ctrl+Shift+M", "Switch between guided and expert mode"),
    "help": ("F1", "Open the user guide"),
    "shortcuts_help": ("Ctrl+/", "Show this list of shortcuts"),
    **{f"tab_{n}": (f"Ctrl+{n}", f"Show tab {n}") for n in range(1, 9)},
}


def _readable(override: str) -> QKeySequence | None:
    sequence = QKeySequence(override)
    # Qt parses any text into *some* sequence ("not a key" becomes N, O, T ...); accept only text it reads back as is
    if not sequence.isEmpty() and sequence.toString().replace(" ", "").lower() == override.replace(" ", "").lower():
        return sequence
    return None


def key_for(action_id: str) -> QKeySequence:
    overrides = userconfig.load()["shortcuts"]
    override = overrides.get(action_id)
    sequence = _readable(override) if override else None
    if sequence is not None:
        # Two actions on one key would both stop working (Qt: "ambiguous shortcut"): an override that collides with
        # another action's key, default or overridden, is ignored.
        taken = {
            (_readable(overrides[other]) or QKeySequence(default)).toString()
            if other in overrides
            else QKeySequence(default).toString()
            for other, (default, _desc) in SHORTCUTS.items()
            if other != action_id
        }
        if sequence.toString() not in taken:
            return sequence
    return QKeySequence(SHORTCUTS[action_id][0])  # no override, or one Qt cannot read: the default stays


class ShortcutsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.resize(560, 520)
        model = QStandardItemModel(0, 3, self)
        model.setHorizontalHeaderLabels(["Action", "Shortcut", "Description"])
        for action_id, (_default, description) in SHORTCUTS.items():
            row = [
                QStandardItem(action_id.replace("_", " ").capitalize()),
                QStandardItem(key_for(action_id).toString(QKeySequence.SequenceFormat.NativeText)),
                QStandardItem(description),
            ]
            for item in row:
                item.setEditable(False)
            model.appendRow(row)
        self.table = named(keyboard_view(QTableView()), "Keyboard shortcuts")
        self.table.setModel(model)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.resizeColumnsToContents()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.addWidget(self.table, 1)
        lay.addWidget(buttons)
        _ = Qt

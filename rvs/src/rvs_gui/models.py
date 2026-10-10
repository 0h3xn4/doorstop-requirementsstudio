"""Qt models for the item table and the findings list."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QBrush, QColor

from rvs_core.adapter import ItemData
from rvs_core.findings import Finding, Severity
from rvs_gui.theme import TOKENS
from rvs_gui.widgets import problem_counts

Index = QModelIndex | QPersistentModelIndex
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    visible: bool = True


COLUMNS = (
    Column("uid", "ID"),
    Column("document", "Document", False),
    Column("title", "Title"),
    Column("type", "Type"),
    Column("status", "Status"),
    Column("priority", "Priority", False),
    Column("owner", "Owner"),
    Column("verify_method", "Method"),
    Column("verify_level", "Level", False),
    Column("parents", "Parents", False),
    Column("problems", "Problems"),
    Column("text", "Statement", False),
)
# Cells that expert mode edits in place (they are attributes of the item, not derived values).
EDITABLE_KEYS = ("title", "type", "status", "priority", "owner", "verify_method", "verify_level")
# Severity text uses text tokens (4.5:1 on the surfaces); "support_warning" is a fill colour and is too pale for text.
_SEVERITY_TOKEN = {Severity.ERROR: "support_error", Severity.WARNING: "warning_text", Severity.INFO: "link"}
HEADER_TIPS = {
    "problems": "E = errors, W = warnings. For example '0E 1W' means no errors and one warning.",
    "text": "The full requirement statement",
}


def severity_color(severity: Severity) -> str:
    return TOKENS[_SEVERITY_TOKEN[severity]]


class ItemTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[ItemData] = []
        self._counts: dict[str, tuple[int, int, int]] = {}
        self._row: dict[str, int] = {}
        self.edit_handler: Callable[[str, str, str], bool] | None = None  # (uid, attribute, value) -> accepted
        self.can_edit: Callable[[ItemData, str], bool] = lambda _item, _key: True
        self.editing_enabled = False

    def set_editing(self, enabled: bool) -> None:
        self.editing_enabled = enabled
        if self._items:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._items) - 1, len(COLUMNS) - 1))

    def flags(self, index: Index) -> Qt.ItemFlag:
        flags = super().flags(index)
        if self.editing_enabled and index.isValid() and self.edit_handler is not None:
            key = COLUMNS[index.column()].key
            if key in EDITABLE_KEYS and self.can_edit(self._items[index.row()], key):
                flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index: Index, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid() or self.edit_handler is None:
            return False
        key = COLUMNS[index.column()].key
        item = self._items[index.row()]
        if key not in EDITABLE_KEYS or not self.editing_enabled:
            return False
        new = "" if value is None else str(value).strip()
        if new == self._value(item, key):
            return False
        return self.edit_handler(item.uid, key, new)

    def set_items(self, items: list[ItemData], counts: dict[str, tuple[int, int, int]]) -> None:
        if self._items and [i.uid for i in items] == [i.uid for i in self._items]:
            # same rows: update in place so selection, scroll position and open editors survive an edit
            self._items = list(items)
            self._counts = counts
            self.dataChanged.emit(self.index(0, 0), self.index(len(items) - 1, len(COLUMNS) - 1))
            return
        self.beginResetModel()
        self._items = list(items)
        self._counts = counts
        self._row = {i.uid: n for n, i in enumerate(self._items)}
        self.endResetModel()

    def row_of(self, uid: str) -> int:
        return self._row.get(uid, -1)

    def item_at(self, row: int) -> ItemData:
        return self._items[row]

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section].title
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.ToolTipRole:
            return HEADER_TIPS.get(COLUMNS[section].key)
        return None

    def _value(self, item: ItemData, key: str) -> str:
        if key == "uid":
            return item.uid
        if key == "document":
            return item.document
        if key == "text":
            return " ".join(item.text.split())
        if key == "parents":
            return ", ".join(item.links)
        if key == "problems":
            e, w, _i = self._counts.get(item.uid, (0, 0, 0))
            return f"{e}E {w}W" if e or w else ""
        value = item.attrs.get(key)
        if key == "title" and not value:
            return item.header
        return "" if value is None else str(value)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        item, key = self._items[index.row()], COLUMNS[index.column()].key
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._value(item, key)
        if role == SORT_ROLE:
            if key == "problems":
                e, w, _i = self._counts.get(item.uid, (0, 0, 0))
                return e * 10_000 + w
            return self._value(item, key)
        if role == Qt.ItemDataRole.ToolTipRole and key in ("text", "title"):
            return item.text
        if role == Qt.ItemDataRole.ToolTipRole and key == "problems":
            e, w, _i = self._counts.get(item.uid, (0, 0, 0))
            return problem_counts(e, w) if e or w else "No problems"
        if role == Qt.ItemDataRole.ForegroundRole and key == "problems":
            e, w, _i = self._counts.get(item.uid, (0, 0, 0))
            if e:
                return QBrush(QColor(TOKENS["support_error"]))
            if w:
                return QBrush(QColor(TOKENS["warning_text"]))
        if role == Qt.ItemDataRole.ForegroundRole and not item.normative:
            return QBrush(QColor(TOKENS["text_secondary"]))
        return None


class ItemFilterProxy(QSortFilterProxyModel):
    """Filters by document, text, status and 'has problems'; sorts problems numerically."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self._document: str | None = None
        self._status = ""
        self._text = ""
        self._only_problems = False

    def _refilter(self) -> None:
        self.beginFilterChange()
        self.endFilterChange()

    def set_document(self, prefix: str | None) -> None:
        self._document = prefix
        self._refilter()

    def set_status(self, status: str) -> None:
        self._status = status
        self._refilter()

    def set_text(self, text: str) -> None:
        self._text = text.strip().lower()
        self._refilter()

    def set_only_problems(self, on: bool) -> None:
        self._only_problems = on
        self._refilter()

    def filterAcceptsRow(self, source_row: int, source_parent: Index) -> bool:
        model = self.sourceModel()
        assert isinstance(model, ItemTableModel)
        item = model.item_at(source_row)
        if self._document and item.document != self._document:
            return False
        if self._status and item.attrs.get("status") != self._status:
            return False
        if self._only_problems and model.index(source_row, [c.key for c in COLUMNS].index("problems")).data() == "":
            return False
        if self._text:
            hay = f"{item.uid} {item.attrs.get('title', '')} {item.header} {item.text}".lower()
            return self._text in hay
        return True


class FindingsModel(QAbstractTableModel):
    HEADERS = ("Severity", "Code", "Item", "Document", "Message", "How to fix")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._findings: list[Finding] = []

    def set_findings(self, findings: list[Finding]) -> None:
        self.beginResetModel()
        self._findings = list(findings)
        self.endResetModel()

    def finding_at(self, row: int) -> Finding:
        return self._findings[row]

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._findings)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        f, col = self._findings[index.row()], index.column()
        if role == Qt.ItemDataRole.UserRole:  # numeric severity rank, used for sorting and tests
            return f.severity.rank
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return f.severity.value
            if col == 1:
                return f.code
            if col == 2:
                return f.uid
            if col == 3:
                return f.uid.rsplit("-", 1)[0] if f.uid else f.location
            if col == 4:
                return f.message
            return f.hint
        if role == Qt.ItemDataRole.ForegroundRole and col == 0:
            return QBrush(QColor(severity_color(f.severity)))
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{f.message}\n{f.hint}\n{f.location}".strip()
        return None

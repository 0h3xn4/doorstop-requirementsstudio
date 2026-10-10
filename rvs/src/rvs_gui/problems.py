"""Problems panel: all findings, sortable by severity and document, with jump-to-item."""

from typing import Any

from PySide6.QtCore import QEvent, QModelIndex, QObject, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rvs_core.findings import Finding, Severity
from rvs_gui.models import FindingsModel, Index
from rvs_gui.widgets import keyboard_view, named, problem_counts

CODE_COLUMN = 1
MAX_COLUMN_WIDTH = 420
SUSPECT_HELP = "A suspect link means a parent item changed after this item was last reviewed."


class FindingsProxy(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.errors_only = False

    def lessThan(self, left: Index, right: Index) -> bool:
        if left.column() == 0:  # severity: by rank, not alphabetically
            return bool(left.data(Qt.ItemDataRole.UserRole) < right.data(Qt.ItemDataRole.UserRole))
        a, b = left.data(), right.data()
        return bool(str(a).lower() < str(b).lower())

    def filterAcceptsRow(self, source_row: int, source_parent: Index) -> bool:
        if not self.errors_only:
            return True
        return bool(self.sourceModel().index(source_row, 0, source_parent).data(Qt.ItemDataRole.UserRole) == 0)


class ProblemsPanel(QDockWidget):
    jump_requested = Signal(str)  # item uid
    location_requested = Signal(str, str)  # (file location, message) for findings without an item

    def __init__(self) -> None:
        super().__init__("Problems")
        self.setObjectName("ProblemsPanel")
        self.model_ = FindingsModel(self)
        self.proxy = FindingsProxy(self)
        self.proxy.setSourceModel(self.model_)
        self.view = named(QTableView(), "Problems")
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        keyboard_view(self.view)
        self.view.verticalHeader().hide()
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setColumnHidden(
            CODE_COLUMN, True
        )  # the code is for the guide and for support, not for the first read
        self.view.setWordWrap(True)
        self.summary = QLabel("No findings.")
        self.errors_only = QCheckBox("Errors only")
        self.errors_only.toggled.connect(self.show_errors_only)
        self.detail = QLabel("Select a problem to read all of it. Press Enter to go to the item.")
        self.detail.setObjectName("Empty")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        named(self.detail, "Problem details")
        top = QHBoxLayout()
        top.addWidget(self.summary, 1)
        top.addWidget(self.errors_only)
        body = QWidget()
        body.setMinimumSize(160, 70)  # the dock can be squeezed; its table then scrolls
        lay = QVBoxLayout(body)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.detail)
        self.setWidget(body)
        self.view.activated.connect(self._on_activated)  # Enter, Return and double-click
        self.view.doubleClicked.connect(self._on_activated)
        self.view.installEventFilter(self)  # Space activates as well
        self.view.selectionModel().currentRowChanged.connect(lambda *_a: self._show_detail())
        self.resize(900, 220)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if obj is self.view and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:  # type: ignore[attr-defined]
            index = self.view.currentIndex()
            if index.isValid():
                self._on_activated(index)
                return True
        return False

    def set_codes_visible(self, visible: bool) -> None:
        self.view.setColumnHidden(CODE_COLUMN, not visible)

    def codes_visible(self) -> bool:
        return not self.view.isColumnHidden(CODE_COLUMN)

    def _show_detail(self) -> None:
        index = self.view.currentIndex()
        if not index.isValid():
            return
        f = self.model_.finding_at(self.proxy.mapToSource(index).row())
        where = f.uid or f.location
        text = (
            f"{f.severity.value.capitalize()} in {where}: {f.message} {f.hint}".strip()
            if where
            else f"{f.message} {f.hint}"
        )
        if f.code.endswith("SUSPECT") or "suspect" in f.message.lower():
            text += f" {SUSPECT_HELP}"
        self.detail.setText(text)

    def restyle(self) -> None:
        if self.model_.rowCount():
            self.model_.dataChanged.emit(
                self.model_.index(0, 0), self.model_.index(self.model_.rowCount() - 1, self.model_.columnCount() - 1)
            )

    def set_findings(self, findings: list[Finding]) -> None:
        self.model_.set_findings(findings)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        e = sum(1 for f in findings if f.severity is Severity.ERROR)
        w = sum(1 for f in findings if f.severity is Severity.WARNING)
        i = sum(1 for f in findings if f.severity is Severity.INFO)
        self.summary.setText(problem_counts(e, w, i) if findings else "No problems.")
        self.view.resizeColumnsToContents()
        for col in range(self.model_.columnCount()):
            if self.view.columnWidth(col) > MAX_COLUMN_WIDTH:
                self.view.setColumnWidth(col, MAX_COLUMN_WIDTH)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.detail.setText(
            "No problems found in this project."
            if not findings
            else "Select a problem to read all of it. Press Enter to go to the item."
        )

    def show_errors_only(self, on: bool) -> None:
        self.proxy.errors_only = on
        self.proxy.beginFilterChange()
        self.proxy.endFilterChange()
        if self.errors_only.isChecked() != on:
            self.errors_only.setChecked(on)

    def _on_activated(self, index: QModelIndex) -> None:
        finding = self.model_.finding_at(self.proxy.mapToSource(index).row())
        if finding.uid:
            self.jump_requested.emit(finding.uid)
        else:
            self.location_requested.emit(finding.location, f"{finding.message} {finding.hint}".strip())

    def data_for_tests(self) -> Any:  # pragma: no cover - convenience for debugging
        return self.model_

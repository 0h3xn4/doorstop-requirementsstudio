"""Problems panel: all findings, sortable by severity and document, with jump-to-item."""

from typing import Any

from PySide6.QtCore import QModelIndex, QObject, QSortFilterProxyModel, Qt, Signal
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
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.verticalHeader().hide()
        self.view.horizontalHeader().setStretchLastSection(True)
        self.summary = QLabel("No findings.")
        self.errors_only = QCheckBox("Errors only")
        self.errors_only.toggled.connect(self.show_errors_only)
        top = QHBoxLayout()
        top.addWidget(self.summary, 1)
        top.addWidget(self.errors_only)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.addLayout(top)
        lay.addWidget(self.view)
        self.setWidget(body)
        self.view.doubleClicked.connect(self._on_double_click)

    def set_findings(self, findings: list[Finding]) -> None:
        self.model_.set_findings(findings)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        e = sum(1 for f in findings if f.severity is Severity.ERROR)
        w = sum(1 for f in findings if f.severity is Severity.WARNING)
        i = sum(1 for f in findings if f.severity is Severity.INFO)
        self.summary.setText(f"{e} errors, {w} warnings, {i} info")
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setStretchLastSection(True)

    def show_errors_only(self, on: bool) -> None:
        self.proxy.errors_only = on
        self.proxy.beginFilterChange()
        self.proxy.endFilterChange()
        if self.errors_only.isChecked() != on:
            self.errors_only.setChecked(on)

    def _on_double_click(self, index: QModelIndex) -> None:
        finding = self.model_.finding_at(self.proxy.mapToSource(index).row())
        if finding.uid:
            self.jump_requested.emit(finding.uid)
        else:
            self.location_requested.emit(finding.location, f"{finding.message} {finding.hint}".strip())

    def data_for_tests(self) -> Any:  # pragma: no cover - convenience for debugging
        return self.model_

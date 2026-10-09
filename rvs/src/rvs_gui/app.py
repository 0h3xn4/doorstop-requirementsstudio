"""Application bootstrap and main window."""

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

import rvs_core
from rvs_gui.dialogs import NewItemDialog
from rvs_gui.doctree import DocumentTree
from rvs_gui.editor import RequirementEditor
from rvs_gui.models import COLUMNS, ItemFilterProxy, ItemTableModel
from rvs_gui.problems import ProblemsPanel
from rvs_gui.session import ProjectSession
from rvs_gui.theme import load_fonts, stylesheet
from rvs_gui.widgets import InlineNotification

TITLE = "Requirements & Verification Studio"
NEW_STATEMENT = "The system shall <describe the required behaviour>."


class FilterBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search ID, title or statement")
        self.search.setClearButtonEnabled(True)
        self.status = QComboBox()
        self.status.setMinimumContentsLength(14)
        self.only_problems = QCheckBox("Only items with problems")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.search, 1)
        lay.addWidget(self.status)
        lay.addWidget(self.only_problems)

    def set_statuses(self, statuses: Sequence[str]) -> None:
        self.status.blockSignals(True)
        self.status.clear()
        self.status.addItem("All statuses")
        self.status.addItems(list(statuses))
        self.status.blockSignals(False)


class MainWindow(QMainWindow):
    def __init__(self, user: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"{TITLE} {rvs_core.__version__}")
        self.resize(1400, 850)
        self.session = ProjectSession(self, user=user)
        self.notification = InlineNotification()
        self.table_model = ItemTableModel(self)
        self.table_proxy = ItemFilterProxy(self)
        self.table_proxy.setSourceModel(self.table_model)
        self.table = QTableView()
        self.table.setModel(self.table_proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)  # keep document/level order until a header is clicked
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.filter_bar = FilterBar()
        self.editor = RequirementEditor(self.session)
        self.doc_tree = DocumentTree()
        self.problems_panel = ProblemsPanel()
        self._syncing = False

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.addWidget(self.filter_bar)
        left_lay.addWidget(self.table)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.editor)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addWidget(self.notification)
        lay.addWidget(split, 1)
        self.setCentralWidget(central)

        tree_dock = QDockWidget("Documents", self)
        tree_dock.setObjectName("DocumentsDock")
        tree_dock.setWidget(self.doc_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tree_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_panel)
        self._build_menus(tree_dock)
        self._connect()
        self.statusBar().showMessage("")

    # menus ####################################################################
    def _build_menus(self, tree_dock: QDockWidget) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        self.action_open = QAction("Open Project…", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.choose_project)
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addActions([self.action_open, quit_action])

        item_menu = bar.addMenu("Item")
        self.action_new = QAction("New Requirement…", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self.new_requirement_dialog)
        self.action_save = QAction("Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(lambda: self.editor.save())
        self.action_revert = QAction("Revert", self)
        self.action_revert.triggered.connect(self.editor.revert)
        item_menu.addActions([self.action_new, self.action_save, self.action_revert])

        view_menu = bar.addMenu("View")
        view_menu.addAction(tree_dock.toggleViewAction())
        view_menu.addAction(self.problems_panel.toggleViewAction())
        self.columns_menu = view_menu.addMenu("Columns")
        self.column_actions: dict[str, QAction] = {}
        for col in COLUMNS:
            act = QAction(col.title, self, checkable=True)
            act.setChecked(col.visible)
            act.toggled.connect(lambda on, key=col.key: self.set_column_visible(key, on))
            self.columns_menu.addAction(act)
            self.column_actions[col.key] = act

        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(self, TITLE, self.about_text()))
        bar.addMenu("Help").addAction(about)
        self._apply_column_visibility()

    def _connect(self) -> None:
        self.session.loaded.connect(self._on_loaded)
        self.session.item_changed.connect(self._on_item_changed)
        self.editor.message.connect(self.notification.show_message)
        self.editor.dirty_changed.connect(lambda _d: self.statusBar().showMessage(self._status_text()))
        self.doc_tree.document_selected.connect(self.table_proxy.set_document)
        self.doc_tree.item_selected.connect(self.select_item)
        self.table.selectionModel().currentRowChanged.connect(self._on_table_row)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._column_menu)
        self.filter_bar.search.textChanged.connect(self.table_proxy.set_text)
        self.filter_bar.status.currentIndexChanged.connect(
            lambda i: self.table_proxy.set_status("" if i <= 0 else self.filter_bar.status.currentText())
        )
        self.filter_bar.only_problems.toggled.connect(self.table_proxy.set_only_problems)
        self.problems_panel.jump_requested.connect(self.select_item)
        self.problems_panel.location_requested.connect(
            lambda loc, msg: self.notification.show_message("info", f"{msg} (see {loc})" if loc else msg)
        )

    def about_text(self) -> str:
        return (
            f"{TITLE}\nrvs {rvs_core.__version__}\ndoorstop {rvs_core.framework_version()}\nOffline: no network access."
        )

    # columns ##################################################################
    def set_column_visible(self, key: str, visible: bool) -> None:
        col = [c.key for c in COLUMNS].index(key)
        self.table.setColumnHidden(col, not visible)
        act = self.column_actions.get(key)
        if act is not None and act.isChecked() != visible:
            act.setChecked(visible)

    def _apply_column_visibility(self) -> None:
        for col in COLUMNS:
            self.table.setColumnHidden(
                [c.key for c in COLUMNS].index(col.key), not self.column_actions[col.key].isChecked()
            )

    def _column_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        for act in self.column_actions.values():
            menu.addAction(act)
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    # project ##################################################################
    def choose_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open project folder")
        if path:
            self.open_project(Path(path))

    def open_project(self, path: Path) -> bool:
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before opening another project.")
            return False
        report = self.session.open(Path(path))
        if report.exit_code == 3 or self.session.cfg is None:
            lines = " ".join(f"{f.message} {f.hint}".strip() for f in report.findings if f.severity.value == "error")
            self.notification.show_message("error", f"The project could not be opened. {lines}")
            return False
        self.notification.dismiss()
        self.setWindowTitle(f"{self.session.cfg.project.name} — {TITLE} {rvs_core.__version__}")
        errors = sum(1 for f in report.findings if f.severity.value == "error")
        if errors:
            self.notification.show_message(
                "warning", f"Opened with {errors} error(s). Double-click a problem in the Problems panel to jump to it."
            )
        return True

    def _status_text(self) -> str:
        s = self.session
        e = sum(1 for f in s.findings if f.severity.value == "error")
        w = sum(1 for f in s.findings if f.severity.value == "warning")
        dirty = " · unsaved changes" if self.editor.is_dirty() else ""
        return f"{len(s.items)} items · {e} errors · {w} warnings{dirty}"

    # model refresh ############################################################
    def _on_loaded(self) -> None:
        s = self.session
        assert s.cfg is not None
        counts = {i.uid: s.counts_for(i.uid) for i in s.items}
        self.table_model.set_items(s.items, counts)
        self._apply_column_visibility()
        self.filter_bar.set_statuses(s.cfg.vocab.values("status"))
        self.doc_tree.populate(s)
        self.problems_panel.set_findings(s.findings)
        self.statusBar().showMessage(self._status_text())
        uid = self.editor.current_uid
        if uid and s.item(uid) is not None:
            if not self.editor.is_dirty():
                self.editor.load(uid)
            self._show_selection(uid)
        elif uid:
            self.editor.current_uid = None

    def _on_item_changed(self, uid: str) -> None:
        self.statusBar().showMessage(self._status_text())

    # selection ################################################################
    def _show_selection(self, uid: str) -> None:
        """Reflect ``uid`` in table and tree without triggering their selection handlers."""
        self._syncing = True
        try:
            row = self.table_model.row_of(uid)
            idx = self.table_proxy.mapFromSource(self.table_model.index(row, 0))
            if row >= 0 and not idx.isValid():  # hidden by a filter: show everything so the item is visible
                self.filter_bar.search.clear()
                self.filter_bar.status.setCurrentIndex(0)
                self.filter_bar.only_problems.setChecked(False)
                self.doc_tree.select_document(None)
                idx = self.table_proxy.mapFromSource(self.table_model.index(row, 0))
            if idx.isValid():
                self.table.selectionModel().setCurrentIndex(
                    idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
                )
                self.table.scrollTo(idx)
            self.doc_tree.show_item(uid)
        finally:
            self._syncing = False

    def _on_table_row(self, current: object, _previous: object) -> None:
        if self._syncing:
            return
        idx = self.table.currentIndex()
        if idx.isValid():
            uid = self.table_proxy.mapToSource(idx).siblingAtColumn(0).data()
            if uid and uid != self.editor.current_uid:
                self.select_item(uid)

    def select_item(self, uid: str) -> bool:
        if self.session.item(uid) is None:
            return False
        if uid == self.editor.current_uid:
            self._show_selection(uid)
            return True
        if self.editor.is_dirty():
            self.notification.show_message(
                "warning", f"{self.editor.current_uid} has unsaved changes. Save or revert them before opening {uid}."
            )
            if self.editor.current_uid:
                self._show_selection(self.editor.current_uid)
            return False
        self.editor.load(uid)
        self._show_selection(uid)
        return True

    # creating #################################################################
    def new_requirement_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        dlg = NewItemDialog(self.session, self)
        if dlg.exec():
            prefix, title, parents = dlg.values()
            self.create_item(prefix, title, parents)

    def create_item(self, prefix: str, title: str, parents: Sequence[str] = ()) -> str | None:
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before creating a new item.")
            return None
        assert self.session.cfg is not None
        attrs = {"title": title or "Untitled", "type": self.session.cfg.vocab.values("type")[0]}
        try:
            item = self.session.create_item(prefix, NEW_STATEMENT, attrs=attrs, parents=list(parents))
        except Exception as exc:  # noqa: BLE001 - friendly message, never a traceback
            self.notification.show_message("error", str(exc))
            return None
        self.select_item(item.uid)
        self.notification.show_message(
            "success", f"Created {item.uid}. Write the statement and set its verification method."
        )
        return item.uid


def create_app(argv: Sequence[str]) -> QApplication:
    app = QApplication.instance() or QApplication(list(argv))
    assert isinstance(app, QApplication)
    load_fonts()
    app.setStyleSheet(stylesheet())
    return app


def create_main_window() -> MainWindow:
    return MainWindow()


def main() -> int:
    app = create_app(sys.argv)
    win = create_main_window()
    win.show()
    return app.exec()

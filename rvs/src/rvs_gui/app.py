"""Application bootstrap and main window."""

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt, Signal
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import rvs_core
from rvs_core.exporters.export_request import ExportRequest, build_output
from rvs_core.exporters.itemsio import ImportReport, apply_import, read_csv, read_xlsx
from rvs_core.matrices import Provenance
from rvs_gui.baseline_dialog import NewBaselineDialog  # noqa: F401
from rvs_gui.baselines_view import BaselinesView
from rvs_gui.changes_view import ChangesView
from rvs_gui.dialogs import NewItemDialog
from rvs_gui.diff_view import DiffView
from rvs_gui.doctree import DocumentTree
from rvs_gui.editor import RequirementEditor
from rvs_gui.export_dialog import ExportDialog
from rvs_gui.graph_view import GraphView
from rvs_gui.impact_panel import ImpactPanel
from rvs_gui.import_dialog import ImportDialog
from rvs_gui.jobs import run_in_background
from rvs_gui.matrix_views import CoverageView, TraceabilityView, VcmView
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
    export_done = Signal(str, str)  # (path, error message or '')

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
        self.impact_panel = ImpactPanel(self.session)
        self.trace_view = TraceabilityView(self.session)
        self.vcm_view = VcmView(self.session)
        self.coverage_view = CoverageView(self.session)
        self.graph_view = GraphView(self.session)
        self.changes_view = ChangesView(self.session)
        self.baselines_view = BaselinesView(self.session)
        self.diff_view = DiffView(self.session)
        self.graph_view.on_node_clicked = self.select_item
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
        self.tabs = QTabWidget()
        self.tabs.addTab(split, "Items")
        self.tabs.addTab(self.trace_view, "Traceability")
        self.tabs.addTab(self.vcm_view, "VCM")
        self.tabs.addTab(self.coverage_view, "Coverage")
        self.tabs.addTab(self.graph_view, "Graph")
        self.tabs.addTab(self.changes_view, "Changes")
        self.tabs.addTab(self.baselines_view, "Baselines")
        self.tabs.addTab(self.diff_view, "Diff")
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addWidget(self.notification)
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        tree_dock = QDockWidget("Documents", self)
        tree_dock.setObjectName("DocumentsDock")
        tree_dock.setWidget(self.doc_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tree_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.impact_panel)
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
        self.action_import = QAction("Import Items…", self)
        self.action_import.setShortcut("Ctrl+I")
        self.action_import.triggered.connect(self.import_items_dialog)
        self.action_export = QAction("Export…", self)
        self.action_export.setShortcut("Ctrl+E")
        self.action_export.triggered.connect(self.export_dialog)
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addActions([self.action_open, self.action_import, self.action_export, quit_action])

        item_menu = bar.addMenu("Item")
        self.action_new = QAction("New Requirement…", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self.new_requirement_dialog)
        self.action_save = QAction("Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(lambda: self.editor.save())
        self.action_revert = QAction("Revert", self)
        self.action_revert.triggered.connect(self.editor.revert)
        self.action_new_ver = QAction("New Verification Item…", self)
        self.action_new_ver.triggered.connect(self.new_verification_dialog)
        item_menu.addActions([self.action_new, self.action_new_ver, self.action_save, self.action_revert])

        project_menu = bar.addMenu("Project")
        self.action_refresh = QAction("Refresh", self)
        self.action_refresh.setShortcut(QKeySequence.StandardKey.Refresh)
        self.action_refresh.triggered.connect(self.session.refresh)
        self.action_full = QAction("Run Full Doorstop Validation", self)
        self.action_full.triggered.connect(self.run_full_validation)
        project_menu.addActions([self.action_refresh, self.action_full])
        project_menu.addSeparator()
        self.action_baseline = QAction("New Baseline…", self)
        self.action_baseline.triggered.connect(self.baselines_view.new_baseline_dialog)
        project_menu.addAction(self.action_baseline)

        view_menu = bar.addMenu("View")
        view_menu.addAction(tree_dock.toggleViewAction())
        view_menu.addAction(self.problems_panel.toggleViewAction())
        view_menu.addAction(self.impact_panel.toggleViewAction())
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
        for cc_view in (self.changes_view, self.baselines_view, self.diff_view):
            cc_view.message.connect(self.notification.show_message)
        self.diff_view.export_done.connect(self.export_done)
        self.baselines_view.compare_requested.connect(self._compare_from_baseline)
        self.session.active_cr_changed.connect(lambda _c: self.statusBar().showMessage(self._status_text()))
        for view in (self.trace_view, self.vcm_view, self.coverage_view):
            view.message.connect(self.notification.show_message)
            view.export_done.connect(self.export_done)
        self.editor.item_loaded.connect(self._on_editor_loaded)
        self.impact_panel.item_requested.connect(self.select_item)
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
        cr = f" · editing under {s.active_cr}" if s.active_cr else ""
        return f"{len(s.items)} items · {e} errors · {w} warnings{cr}{dirty}"

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

    def _on_editor_loaded(self, uid: str) -> None:
        self.impact_panel.set_item(uid)
        self.graph_view.show_item(uid)

    # export / import ###########################################################
    def export_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        dlg = ExportDialog(self.session, self, current_uid=self.editor.current_uid or "")
        if dlg.exec():
            if not dlg.path.text().strip():
                self.notification.show_message("warning", "Choose a file name for the export.")
                return
            self.export_to(dlg.request(), dlg.destination())

    def export_to(self, request: ExportRequest, path: Path) -> None:
        """Build and write ``request`` to ``path`` on a worker thread; the window stays usable."""
        s = self.session
        if s.cfg is None or s.graph is None:
            self.notification.show_message("info", "Open a project first.")
            return
        cfg, items, graph, user, label = s.cfg, list(s.items), s.graph, s.user, s.baseline_label

        def work() -> str:
            data = build_output(request, cfg, items, graph, Provenance.now(cfg, user=user, baseline=label))
            path.write_bytes(data)
            return str(path)

        def done(written: str) -> None:
            self.notification.show_message("success", f"Exported to {written}.")
            self.export_done.emit(written, "")

        def failed(exc: Exception) -> None:
            if isinstance(exc, OSError):
                text = f"The file {path} could not be written: {exc.strerror}. Choose another location."
            elif isinstance(exc, ValueError):
                text = str(exc)
            else:
                text = f"The export to {path} failed: {exc}"
            self.notification.show_message("error", text)
            self.export_done.emit(str(path), text)

        self.notification.show_message("info", f"Exporting to {path} …")
        run_in_background(work, done, failed)

    def import_items_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        chosen, _ = QFileDialog.getOpenFileName(self, "Import items", "", "Item tables (*.csv *.xlsx)")
        if not chosen:
            return
        rows = self.read_import_file(Path(chosen))
        if rows is None:
            return
        dlg = ImportDialog(self.session, rows, self)
        if dlg.exec():
            self.apply_import(dlg.plan, why=dlg.reason.text(), skip_errors=dlg.skip_errors.isChecked())

    def read_import_file(self, path: Path) -> list[dict[str, str]] | None:
        suffix = path.suffix.lower()
        if suffix not in (".csv", ".xlsx"):
            self.notification.show_message("error", f"{path.name} cannot be imported: the file must be .csv or .xlsx.")
            return None
        try:
            data = path.read_bytes()
            return read_csv(data) if suffix == ".csv" else read_xlsx(data)
        except Exception as exc:  # noqa: BLE001 - corrupt or unreadable file: plain message, no traceback
            self.notification.show_message(
                "error", f"{path.name} could not be read ({exc}). Check that it is an item table exported by RVS."
            )
            return None

    def apply_import(self, plan: object, why: str = "", skip_errors: bool = False) -> ImportReport | None:
        from rvs_core.exporters.itemsio import ImportPlan

        assert isinstance(plan, ImportPlan) and self.session.root is not None
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before importing.")
            return None
        try:
            report = apply_import(self.session.root, plan, user=self.session.user, why=why, skip_errors=skip_errors)
        except Exception as exc:  # noqa: BLE001 - friendly message
            self.notification.show_message(
                "error",
                f"The import stopped: {exc}. Items processed before the problem were written; check the Problems panel.",
            )
            self.session.refresh()
            return None
        self.session.refresh()
        if not report.applied:
            self.notification.show_message("error", f"{report.errors} row(s) have errors, so nothing was imported.")
        else:
            self.notification.show_message(
                "success",
                f"Imported: {report.created} created, {report.updated} updated, {report.unchanged} unchanged"
                + (f", {report.errors} skipped." if report.errors else "."),
            )
        return report

    def _compare_from_baseline(self, name: str) -> None:
        self.diff_view.set_range(name, None)
        self.tabs.setCurrentWidget(self.diff_view)
        self.diff_view.compare()

    def run_full_validation(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        self.session.run_full_validation()
        self.notification.show_message(
            "info", "Full Doorstop validation finished; its findings are in the Problems panel until the next edit."
        )

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

    def new_verification_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        dlg = NewItemDialog(self.session, self, kind="verification")
        if dlg.exec():
            prefix, _title, targets = dlg.values()
            self.create_verification(prefix, targets)

    def create_verification(self, prefix: str, targets: Sequence[str]) -> str | None:
        """New verification item (planned) that verifies ``targets``; method and level follow the first target."""
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before creating a new item.")
            return None
        assert self.session.cfg is not None
        first = self.session.item(targets[0]) if targets else None
        vocab = self.session.cfg.vocab
        attrs = {
            "title": f"Verify {', '.join(targets)}" if targets else "Verification",
            "verify_method": (first.attrs.get("verify_method") if first else None) or vocab.values("verify_method")[0],
            "verify_level": (first.attrs.get("verify_level") if first else None) or vocab.values("verify_level")[0],
            "link_verifies": list(targets),
        }
        text = f"Verify {', '.join(targets)}." if targets else "Describe the verification activity."
        try:
            item = self.session.create_item(prefix, text, attrs=attrs, derived=True)
        except Exception as exc:  # noqa: BLE001 - friendly message, never a traceback
            self.notification.show_message("error", str(exc))
            return None
        self.select_item(item.uid)
        self.notification.show_message(
            "success", f"Created {item.uid} (planned). Describe the procedure and set its status."
        )
        return item.uid

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

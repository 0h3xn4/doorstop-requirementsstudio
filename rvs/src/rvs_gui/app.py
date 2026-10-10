"""Application bootstrap and main window."""

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import (
    QAbstractItemModel,
    QByteArray,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import rvs_core
from rvs_core import userconfig
from rvs_core.adapter import ItemData, ProjectError
from rvs_core.authoring import ReasonRequiredError
from rvs_core.exporters.export_request import ExportRequest, build_output
from rvs_core.exporters.itemsio import ImportReport, apply_import, read_csv, read_xlsx
from rvs_core.exporters.reqif import read_reqif
from rvs_core.matrices import Provenance
from rvs_core.validate import ValidationReport
from rvs_gui import theme as _theme
from rvs_gui.baseline_dialog import NewBaselineDialog  # noqa: F401
from rvs_gui.baselines_view import BaselinesView
from rvs_gui.changes_view import ChangesView
from rvs_gui.dialogs import NewItemDialog
from rvs_gui.diff_view import DiffView
from rvs_gui.doctree import DocumentTree
from rvs_gui.editor import RequirementEditor
from rvs_gui.export_dialog import ExportDialog
from rvs_gui.glossary_dialog import GlossaryDialog
from rvs_gui.graph_view import GraphView
from rvs_gui.help_viewer import HelpViewer
from rvs_gui.impact_panel import ImpactPanel
from rvs_gui.import_dialog import ImportDialog
from rvs_gui.jobs import run_in_background
from rvs_gui.matrix_views import CoverageView, TraceabilityView, VcmView
from rvs_gui.models import COLUMNS, ItemFilterProxy, ItemTableModel
from rvs_gui.problems import ProblemsPanel
from rvs_gui.project_dialogs import NewProjectDialog
from rvs_gui.session import ProjectSession
from rvs_gui.shortcuts import SHORTCUTS, ShortcutsDialog, key_for
from rvs_gui.theme import load_fonts, stylesheet
from rvs_gui.widgets import InlineNotification
from rvs_gui.wizard import NewRequirementWizard, RequirementSpec

TITLE = "Requirements & Verification Studio"
NEW_STATEMENT = "The system shall <describe the required behaviour>."
MODES = ("guided", "expert")
ROW_HEIGHT = {"guided": 30, "expert": 22}
ENUM_KEYS = ("type", "status", "priority", "verify_method", "verify_level")


class EnumDelegate(QStyledItemDelegate):
    """Combo box limited to the project vocabulary of the cell's attribute."""

    def __init__(self, choices: Callable[[QModelIndex], list[str]], parent: QWidget) -> None:
        super().__init__(parent)
        self._choices = choices

    def createEditor(self, parent: QWidget, option: object, index: QModelIndex) -> QWidget:  # type: ignore[override]
        combo = QComboBox(parent)
        combo.addItems(self._choices(index))
        return combo

    def setEditorData(self, editor: QWidget, index: QModelIndex | QPersistentModelIndex) -> None:
        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(0, editor.findText(str(index.data(Qt.ItemDataRole.EditRole)))))

    def setModelData(
        self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


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

    def set_statuses(self, statuses: Sequence[str]) -> bool:
        """Refill the status choices, keeping the selected one. Returns False if it no longer exists (the filter was
        reset to 'All statuses', and the caller must reset the table filter too)."""
        keep = self.status.currentText() if self.status.currentIndex() > 0 else ""
        self.status.blockSignals(True)
        self.status.clear()
        self.status.addItem("All statuses")
        self.status.addItems(list(statuses))
        found = self.status.findText(keep) if keep else 0
        self.status.setCurrentIndex(max(found, 0))
        self.status.blockSignals(False)
        return not keep or found > 0


class MainWindow(QMainWindow):
    export_done = Signal(str, str)  # (path, error message or '')
    project_opened = Signal(bool)  # an asynchronous open finished (True = the project is now open)

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
        self._opening = False
        self._help: HelpViewer | None = None
        self.mode = "guided"
        self.theme = "light"
        self.actions_by_id: dict[str, QAction] = {}

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
        self.mode_label = QLabel()
        self.statusBar().addPermanentWidget(self.mode_label)
        self.resizeDocks([self.problems_panel], [120], Qt.Orientation.Vertical)  # the editor needs the height more
        self._build_menus(tree_dock)
        self._connect()
        self._setup_inline_editing()
        self.statusBar().showMessage("")
        self.set_mode(userconfig.load()["mode"], remember=False)
        self.set_theme(userconfig.load()["theme"], remember=False, restyle=False)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_scheme)
        self._restore_geometry()

    # menus ####################################################################
    def _action(self, action_id: str, text: str, slot: Callable[[], object], menu: QMenu | None = None) -> QAction:
        act = QAction(text, self)
        act.setShortcut(key_for(action_id))
        act.triggered.connect(lambda _checked=False: slot())
        act.setToolTip(SHORTCUTS[action_id][1])
        self.addAction(act)  # also active when the action is in no menu (tab switching)
        self.actions_by_id[action_id] = act
        if menu is not None:
            menu.addAction(act)
        return act

    def _tab_slot(self, index: int) -> Callable[[], None]:
        return lambda: self.tabs.setCurrentIndex(index)

    def _build_menus(self, tree_dock: QDockWidget) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        self.action_open = self._action("open_project", "Open Project…", self.choose_project, file_menu)
        self.action_new_project = self._action("new_project", "New Project…", self.new_project_dialog, file_menu)
        self.recent_menu = file_menu.addMenu("Open Recent")
        self.examples_menu = file_menu.addMenu("Open Example")
        for key, title in (("minimal", "Minimal (10 items)"), ("satellite", "Small satellite (about 300 items)")):
            act = QAction(title, self)
            act.triggered.connect(lambda _c=False, k=key: self.open_example_dialog(k))
            self.examples_menu.addAction(act)
        file_menu.addSeparator()
        self.action_import = self._action("import_items", "Import Items…", self.import_items_dialog, file_menu)
        self.action_export = self._action("export", "Export…", self.export_dialog, file_menu)
        file_menu.addSeparator()
        self._action("quit", "Quit", self.close, file_menu)

        item_menu = bar.addMenu("Item")
        self.action_new = self._action("new_requirement", "New Requirement…", self.new_requirement_dialog, item_menu)
        self.action_new_ver = self._action(
            "new_verification", "New Verification Item…", self.new_verification_dialog, item_menu
        )
        self.action_save = self._action("save", "Save", lambda: self.editor.save(), item_menu)
        self.action_revert = self._action("revert", "Revert", self.editor.revert, item_menu)
        item_menu.addSeparator()
        self._action("find", "Search Items", self.focus_search, item_menu)
        self._action("go_to", "Go to Item…", self.go_to_dialog, item_menu)
        self._action("next_problem", "Next Problem", self.next_problem, item_menu)
        self._action("prev_problem", "Previous Problem", self.previous_problem, item_menu)
        self._action("focus_problems", "Problems Panel", self.focus_problems, item_menu)

        project_menu = bar.addMenu("Project")
        self.action_refresh = self._action("refresh", "Refresh", self.session.refresh, project_menu)
        self.action_full = self._action(
            "full_validation", "Run Full Doorstop Validation", self.run_full_validation, project_menu
        )
        project_menu.addSeparator()
        self.action_baseline = self._action(
            "new_baseline", "New Baseline…", self.baselines_view.new_baseline_dialog, project_menu
        )
        self.action_glossary = self._action("glossary", "Glossary and Acronyms…", self.glossary_dialog, project_menu)

        view_menu = bar.addMenu("View")
        mode_menu = view_menu.addMenu("Mode")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.action_mode_guided = QAction("Guided: wizard, help under every field", self, checkable=True)
        self.action_mode_expert = QAction("Expert: dense table, edit in place", self, checkable=True)
        for mode, act in (("guided", self.action_mode_guided), ("expert", self.action_mode_expert)):
            act.triggered.connect(lambda _c=False, m=mode: self.set_mode(m))
            group.addAction(act)
            mode_menu.addAction(act)
        self._action("toggle_mode", "Switch Mode", self.toggle_mode, mode_menu)
        theme_menu = view_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        for name, label in (("light", "Light"), ("dark", "Dark"), ("system", "Follow the system")):
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda _c=False, n=name: self.set_theme(n))
            theme_group.addAction(act)
            theme_menu.addAction(act)
            setattr(self, f"action_theme_{name}", act)
        view_menu.addSeparator()
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
        tabs_menu = view_menu.addMenu("Tabs")
        for n in range(1, self.tabs.count() + 1):
            self._action(f"tab_{n}", self.tabs.tabText(n - 1), self._tab_slot(n - 1), tabs_menu)
        for n in range(self.tabs.count() + 1, 9):  # shortcuts for tabs that do not exist are still bound, harmlessly
            self._action(f"tab_{n}", f"Tab {n}", lambda: None)

        help_menu = bar.addMenu("Help")
        self._action("help", "User Guide", lambda: self.show_help(), help_menu)
        self._action("shortcuts_help", "Keyboard Shortcuts", self.show_shortcuts, help_menu)
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(self, TITLE, self.about_text()))
        help_menu.addAction(about)
        self._apply_column_visibility()
        self._refresh_recent()

    def _connect(self) -> None:
        self.session.loaded.connect(self._on_loaded)
        self.session.load_failed.connect(lambda text: self.notification.show_message("error", text))
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
        if self._opening:
            self.notification.show_message("info", "A project is being opened. Please wait a moment.")
            return False
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before opening another project.")
            return False
        return self._finish_open(Path(path), ProjectSession.open_report(Path(path)))

    def open_project_async(self, path: Path) -> None:
        """Open ``path`` without freezing the window (large projects take seconds); ``project_opened`` reports the result."""
        path = Path(path)
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before opening another project.")
            self.project_opened.emit(False)
            return
        if self._opening:
            self.notification.show_message("info", "A project is already being opened. Please wait.")
            self.project_opened.emit(False)
            return
        self._opening = True
        self.notification.show_message("info", f"Opening {path} …")

        def done(report: object) -> None:
            self._opening = False
            if self.editor.is_dirty():  # the user started editing while the project was loading
                self.notification.show_message(
                    "warning",
                    "The project was not opened because you started editing. Save or revert, then open it again.",
                )
                self.project_opened.emit(False)
                return
            self.project_opened.emit(self._finish_open(path, report))  # type: ignore[arg-type]

        def failed(exc: Exception) -> None:
            self._opening = False
            self.notification.show_message("error", f"The project could not be opened: {exc}")
            self.project_opened.emit(False)

        run_in_background(lambda: ProjectSession.open_report(path), done, failed)

    def _finish_open(self, path: Path, report: ValidationReport) -> bool:
        self.session.adopt(path, report)
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
        userconfig.add_recent(path)
        self._refresh_recent()
        return True

    def _refresh_recent(self) -> None:
        self.recent_menu.clear()
        recent = [p for p in userconfig.recent_projects() if p.is_dir()]  # a moved or deleted project is not offered
        for path in recent:
            act = QAction(str(path), self)
            act.triggered.connect(lambda _c=False, p=path: self.open_project(p))
            self.recent_menu.addAction(act)
        self.recent_menu.setEnabled(bool(recent))

    def new_project_dialog(self) -> None:
        dlg = NewProjectDialog(self)
        try:
            if dlg.exec():
                self.create_project(*dlg.values())
        finally:
            dlg.deleteLater()

    def create_project(self, folder: Path, name: str, template: str, git: bool) -> bool:
        from rvs_core.project_templates import create_from_template

        if self._opening:
            self.notification.show_message("info", "A project is being opened. Please wait a moment.")
            return False
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before creating a project.")
            return False
        if not str(folder).strip() or str(folder) == ".":
            self.notification.show_message("error", "Choose a folder for the new project.")
            return False
        try:
            create_from_template(Path(folder), name, template, git=git)
        except (ValueError, OSError) as exc:
            self.notification.show_message("error", str(exc))
            return False
        return self.open_project(Path(folder))

    def open_example_dialog(self, key: str) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Where should the example project be created?")
        if chosen:
            self.open_example(key, Path(chosen) / f"rvs-example-{key}")

    def open_example(self, key: str, target: Path) -> bool:
        """Generate an example project (fictional data) at ``target`` and open it."""
        from rvs_core.examples.minimal import build_minimal_project
        from rvs_core.examples.satellite import build_satellite_project

        builders = {"minimal": build_minimal_project, "satellite": build_satellite_project}
        if key not in builders:
            self.notification.show_message("error", f"There is no example called '{key}'. Choose minimal or satellite.")
            return False
        target = Path(target)
        if target.exists() and any(target.iterdir()):
            self.notification.show_message("error", f"{target} already exists and is not empty. Choose another folder.")
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            builders[key](target)
        except OSError as exc:
            self.notification.show_message("error", f"The example could not be created in {target}: {exc.strerror}.")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        return self.open_project(target)

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
        if not self.filter_bar.set_statuses(s.cfg.vocab.values("status")):
            self.table_proxy.set_status("")  # the filtered status was removed from the vocabulary
        self.doc_tree.populate(s)
        self.problems_panel.set_findings(s.findings)
        self.statusBar().showMessage(self._status_text())
        uid = self.editor.current_uid
        if uid and s.item(uid) is not None:
            if not self.editor.is_dirty():
                self.editor.load(uid)
            self._show_selection(uid)
        elif uid:  # the item is gone (another project, or deleted): nothing may stay bound to it
            self.editor.clear()
            self.impact_panel.clear()
            self.graph_view.uid = None
            self.graph_view.refresh()

    def _on_editor_loaded(self, uid: str) -> None:
        self.impact_panel.set_item(uid)
        self.graph_view.show_item(uid)

    # export / import ###########################################################
    def export_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        dlg = ExportDialog(self.session, self, current_uid=self.editor.current_uid or "")
        try:
            if dlg.exec():
                if not dlg.path.text().strip():
                    self.notification.show_message("warning", "Choose a file name for the export.")
                    return
                self.export_to(dlg.request(), dlg.destination())
        finally:
            dlg.deleteLater()

    def export_to(self, request: ExportRequest, path: Path) -> None:
        """Build and write ``request`` to ``path`` on a worker thread; the window stays usable."""
        s = self.session
        if s.cfg is None or s.graph is None:
            self.notification.show_message("info", "Open a project first.")
            return
        if path.exists() and not self.confirm_overwrite(path):
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
        if self._refuse_while_dirty("importing"):
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Import items", "", "Item tables and ReqIF files (*.csv *.xlsx *.reqif)"
        )
        if not chosen:
            return
        rows = self.read_import_file(Path(chosen))
        if rows is None:
            return
        dlg = ImportDialog(self.session, rows, self)
        try:
            if dlg.exec():
                self.apply_import(dlg.plan, why=dlg.reason.text(), skip_errors=dlg.skip_errors.isChecked())
        finally:
            dlg.deleteLater()

    def read_import_file(self, path: Path) -> list[dict[str, str]] | None:
        suffix = path.suffix.lower()
        if suffix not in (".csv", ".xlsx", ".reqif"):
            self.notification.show_message(
                "error", f"{path.name} cannot be imported: the file must be .csv, .xlsx or .reqif."
            )
            return None
        try:
            data = path.read_bytes()
            if suffix == ".reqif":
                return self._read_reqif(data)
            return read_csv(data) if suffix == ".csv" else read_xlsx(data)
        except Exception as exc:  # noqa: BLE001 - corrupt or unreadable file: plain message, no traceback
            self.notification.show_message(
                "error",
                f"{path.name} could not be read ({exc}). "
                + (
                    "Check that it is a ReqIF file."
                    if suffix == ".reqif"
                    else "Check that it is an item table exported by RVS."
                ),
            )
            return None

    def _read_reqif(self, data: bytes, document: str | None = None) -> list[dict[str, str]] | None:
        """Rows of a ReqIF file; asks which document to use when its specifications do not name one."""
        s = self.session
        assert s.cfg is not None
        try:
            read = read_reqif(data, s.cfg, s.items, document=document)
        except ValueError as exc:
            if document is None and "does not match a document" in str(exc):
                choice, ok = QInputDialog.getItem(
                    self,
                    "Import ReqIF",
                    f"{exc}\n\nImport into which document?",
                    [d.prefix for d in s.cfg.project.documents],
                    0,
                    False,
                )
                return self._read_reqif(data, choice) if ok else None
            raise
        notes = list(read.notes)
        if read.unmapped:
            notes.append(f"Not imported (no matching field): {', '.join(read.unmapped)}.")
        if notes:
            self.notification.show_message("info", " ".join(notes))
        return read.rows

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
                self.table_proxy.set_status("")  # setCurrentIndex(0) is a no-op when it already shows 'All statuses'
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

    # modes ####################################################################
    def set_mode(self, mode: str, remember: bool = True) -> None:
        """Guided: wizard, help under each field, roomy read-only table. Expert: dense table, edit in place."""
        if mode not in MODES:
            raise ValueError(f"Unknown mode '{mode}'. Use guided or expert.")
        self.mode = mode
        expert = mode == "expert"
        self.action_mode_guided.setChecked(not expert)
        self.action_mode_expert.setChecked(expert)
        self.editor.set_help_visible(not expert)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT[mode])
        self.table_model.set_editing(expert)
        triggers = (
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
            if expert
            else QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setEditTriggers(triggers)
        self.mode_label.setText("Expert mode" if expert else "Guided mode")
        if remember:
            userconfig.update(mode=mode)

    def set_theme(self, name: str, remember: bool = True, restyle: bool = True) -> None:
        """Light, dark, or follow the desktop. Applies at once and is remembered.

        The application stylesheet is replaced when the program set one at start-up (``create_app``); a window created
        without it (tests, embedding) is styled on its own, which also keeps the cost to this window's widgets."""
        _theme.set_theme(name)  # raises ValueError for an unknown name
        self.theme = name
        for key in _theme.THEMES:
            getattr(self, f"action_theme_{key}").setChecked(key == name)
        if restyle:
            load_fonts()
            app = QApplication.instance()
            if isinstance(app, QApplication) and app.styleSheet():
                app.setStyleSheet(stylesheet())
            else:
                self.setStyleSheet(stylesheet())
            self._restyle()
        if remember:
            userconfig.update(theme=name)

    def _on_system_scheme(self, _scheme: object = None) -> None:
        """The desktop switched between light and dark: follow it, but only if the user chose "Follow the system"."""
        if self.theme == "system":
            self.set_theme("system", remember=False)

    def _restyle(self) -> None:
        """Repaint what bakes colours in at creation time."""
        self.notification.restyle()
        for view in (self.trace_view, self.vcm_view, self.coverage_view):
            view.restyle()
        self.editor.restyle()
        self.graph_view.refresh()
        self.diff_view.restyle()
        if self.table_model.rowCount():
            self.table_model.dataChanged.emit(
                self.table_model.index(0, 0),
                self.table_model.index(self.table_model.rowCount() - 1, self.table_model.columnCount() - 1),
            )
        self.problems_panel.restyle()
        if self._help is not None:
            self._help.restyle()

    def toggle_mode(self) -> None:
        self.set_mode("guided" if self.mode == "expert" else "expert")

    # inline editing (expert mode) ##############################################
    def _setup_inline_editing(self) -> None:
        self.table_model.edit_handler = self.inline_edit
        self.table_model.can_edit = self._can_edit_cell
        for key in ENUM_KEYS:
            col = [c.key for c in COLUMNS].index(key)
            self.table.setItemDelegateForColumn(col, EnumDelegate(self._choices_for, self.table))

    def _can_edit_cell(self, item: ItemData, key: str) -> bool:
        cfg = self.session.cfg
        decl = cfg.project.document(item.document) if cfg else None
        return decl is not None and cfg is not None and key in cfg.attribute_defs(decl.kind)

    def _choices_for(self, index: QModelIndex) -> list[str]:
        cfg = self.session.cfg
        assert cfg is not None
        source = self.table_proxy.mapToSource(index) if index.model() is self.table_proxy else index
        item = self.table_model.item_at(source.row())
        key = COLUMNS[source.column()].key
        decl = cfg.project.document(item.document)
        adef = cfg.attribute_defs(decl.kind if decl else "requirements").get(key)
        if adef is None or not adef.vocab:
            return []
        values = list(cfg.vocab.values(adef.vocab))
        return values if adef.required else ["", *values]

    def ask_reason(self, uid: str) -> str:
        text, ok = QInputDialog.getText(
            self, "Reason for change", f"{uid} is baselined, so every change needs a reason. Why are you changing it?"
        )
        return text.strip() if ok else ""

    def inline_edit(self, uid: str, key: str, value: str) -> bool:
        """Apply one cell edit from the table. Returns False (with a message) when the edit is refused."""
        if self.editor.is_dirty() and self.editor.current_uid == uid:
            self.notification.show_message(
                "warning", f"Save or revert your changes to {uid} before editing it in the table."
            )
            return False
        why = ""
        for _attempt in range(2):
            try:
                self.session.update_item(uid, attrs={key: value}, why=why)
            except ReasonRequiredError as exc:
                why = self.ask_reason(uid)
                if not why.strip():
                    self.notification.show_message("error", f"{exc} The change was not made: a reason is required.")
                    return False
            except (ValueError, ProjectError) as exc:
                self.notification.show_message("error", str(exc))
                return False
            except OSError as exc:
                self.notification.show_message("error", f"{uid} could not be saved ({exc.strerror or exc}).")
                return False
            else:
                return True
        return False

    # navigation ################################################################
    def focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.filter_bar.search.setFocus()
        self.filter_bar.search.selectAll()

    def go_to_dialog(self) -> None:
        text, ok = QInputDialog.getText(self, "Go to item", "Item ID (for example SYS-0012):")
        if ok and text.strip():
            self.go_to(text)

    def go_to(self, text: str) -> bool:
        uid = text.strip().upper()
        if self.session.item(uid) is None:
            self.notification.show_message("warning", f"There is no item {uid or text!r} in this project.")
            return False
        self.tabs.setCurrentIndex(0)
        return self.select_item(uid)

    def problem_uids(self) -> list[str]:
        return [
            i.uid
            for i in self.session.items
            if any(f.severity.value in ("error", "warning") for f in self.session.findings_for(i.uid))
        ]

    def _step_problem(self, step: int) -> str | None:
        uids = self.problem_uids()
        if not uids:
            self.notification.show_message("success", "No problems to go to.")
            return None
        current = self.editor.current_uid
        if current in uids:
            target = uids[(uids.index(current) + step) % len(uids)]
        else:  # not itself a problem: the neighbour in table order, wrapping around
            order = {i.uid: n for n, i in enumerate(self.session.items)}
            here = order.get(current or "", -1)
            after = [u for u in uids if order[u] > here]
            before = [u for u in uids if order[u] < here]
            target = (after[0] if after else uids[0]) if step > 0 else (before[-1] if before else uids[-1])
        self.tabs.setCurrentIndex(0)
        return target if self.select_item(target) else None

    def next_problem(self) -> str | None:
        return self._step_problem(1)

    def previous_problem(self) -> str | None:
        return self._step_problem(-1)

    def focus_problems(self) -> None:
        self.problems_panel.show()
        self.problems_panel.raise_()
        self.problems_panel.setFocus()

    # dialogs ###################################################################
    def glossary_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        dlg = GlossaryDialog(self.session, self)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def show_shortcuts(self) -> None:
        dlg = ShortcutsDialog(self)
        try:
            dlg.exec()
        finally:
            dlg.deleteLater()

    def show_help(self, anchor: str = "") -> HelpViewer:
        if self._help is None:
            self._help = HelpViewer(self)  # owned by the main window: closing the window closes the guide
        self._help.show_section(anchor)
        self._help.show()
        self._help.raise_()
        return self._help

    def _restore_geometry(self) -> None:
        raw = userconfig.load()["geometry"]
        if raw:
            self.restoreGeometry(QByteArray.fromBase64(raw.encode("ascii")))

    def ask_unsaved(self) -> str:
        """'save', 'discard' or 'cancel': what to do with edits that are not saved (overridden in tests)."""
        box = QMessageBox(
            QMessageBox.Icon.Question,
            TITLE,
            f"{self.editor.current_uid} has unsaved changes.",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            self,
        )
        answer = box.exec()
        return {
            QMessageBox.StandardButton.Save: "save",
            QMessageBox.StandardButton.Discard: "discard",
        }.get(QMessageBox.StandardButton(answer), "cancel")

    def confirm_overwrite(self, path: Path) -> bool:
        answer = QMessageBox.question(
            self,
            TITLE,
            f"{path.name} already exists. Replace it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self.editor.is_dirty():
            choice = self.ask_unsaved()
            if choice == "cancel" or (choice == "save" and not self.editor.save()):
                event.ignore()
                return
        if self._help is not None:
            self._help.close()
        userconfig.update(geometry=bytes(self.saveGeometry().toBase64().data()).decode("ascii"))
        super().closeEvent(event)

    # creating #################################################################
    def new_requirement_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        if self._refuse_while_dirty("creating a new item"):
            return
        current = self.session.item(self.editor.current_uid or "")
        document = current.document if current and self.session.kind_of(current.document) == "requirements" else None
        if self.mode == "guided":
            wizard = NewRequirementWizard(self.session, self, document=document)
            try:
                if wizard.exec():
                    self.create_from_spec(wizard.spec())
            finally:
                wizard.deleteLater()
            return
        dlg = NewItemDialog(self.session, self, document=document)
        try:
            if dlg.exec():
                prefix, title, parents = dlg.values()
                self.create_item(prefix, title, parents)
        finally:
            dlg.deleteLater()

    def _refuse_while_dirty(self, what: str) -> bool:
        """True (with a message) when edits are pending: ask for them to be saved *before* the user fills in a dialog."""
        if self.editor.is_dirty():
            self.notification.show_message("warning", f"Save or revert your changes before {what}.")
            return True
        return False

    def create_from_spec(self, spec: RequirementSpec) -> str | None:
        """Create the requirement collected by the wizard and, if asked, its planned verification item."""
        if self.editor.is_dirty():
            self.notification.show_message("warning", "Save or revert your changes before creating a new item.")
            return None
        try:
            item = self.session.create_item(spec.document, spec.text, attrs=spec.attrs, parents=spec.parents)
        except Exception as exc:  # noqa: BLE001 - friendly message, never a traceback
            self.notification.show_message("error", str(exc))
            return None
        extra = ""
        if spec.verification is not None:
            try:
                vocab = self.session.cfg.vocab  # type: ignore[union-attr]
                ver = self.session.create_item(
                    spec.verification.document,
                    f"Verify {item.uid}.",
                    attrs={
                        "title": f"Verify {item.uid}",
                        "verify_method": spec.attrs.get("verify_method") or vocab.values("verify_method")[0],
                        "verify_level": spec.attrs.get("verify_level") or vocab.values("verify_level")[0],
                        "link_verifies": [item.uid],
                    },
                    derived=True,
                )
                extra = f" and the planned verification item {ver.uid}"
            except Exception as exc:  # noqa: BLE001
                self.select_item(item.uid)
                self.notification.show_message(
                    "warning", f"Created {item.uid}, but its verification item could not be created: {exc}"
                )
                return item.uid
        self.select_item(item.uid)
        self.notification.show_message("success", f"Created {item.uid}{extra}.")
        return item.uid

    def new_verification_dialog(self) -> None:
        if self.session.cfg is None:
            self.notification.show_message("info", "Open a project first.")
            return
        if self._refuse_while_dirty("creating a new item"):
            return
        dlg = NewItemDialog(self.session, self, kind="verification")
        try:
            if dlg.exec():
                prefix, _title, targets = dlg.values()
                self.create_verification(prefix, targets)
        finally:
            dlg.deleteLater()

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
    _theme.set_theme(userconfig.load()["theme"])
    app.setStyleSheet(stylesheet())
    return app


def create_main_window() -> MainWindow:
    return MainWindow()


def main() -> int:
    from rvs_gui.crash import install_excepthook

    install_excepthook()
    app = create_app(sys.argv)
    win = create_main_window()
    win.show()
    return app.exec()

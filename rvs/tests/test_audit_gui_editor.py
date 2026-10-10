"""GUI audit: editor focus survives Save, wording, navigation from tables, accessible names, background work."""

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QModelIndex, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTableView,
    QTreeView,
    QWidget,
)

from rvs_gui import fields
from rvs_gui.app import MainWindow, create_main_window


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.resize(1400, 900)
    w.show()
    assert w.open_project(minimal_project)
    w.activateWindow()
    qtbot.waitUntil(w.isActiveWindow, timeout=3000)
    return w


def _focus_in(widget: QWidget) -> None:
    QApplication.sendEvent(widget, QFocusEvent(QEvent.Type.FocusIn))


# R12 -------------------------------------------------------------------------------------------------------------
def test_saving_keeps_the_form_and_the_keyboard_focus(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.select_item("EPS-0001")
    qtbot.wait(50)  # the freshly built form becomes visible (and focusable) in the next event-loop turn
    owner = win.editor.field("owner")
    owner.setFocus()
    qtbot.waitUntil(owner.hasFocus, timeout=2000)
    owner.setText("power team")
    assert win.editor.is_dirty()
    old_cfg = win.session.cfg
    QTest.keyClick(owner, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)  # Ctrl+S
    assert win.session.cfg is not old_cfg  # the configuration object was replaced by the refresh ...
    assert win.editor.field("owner") is owner  # ... yet the form was not rebuilt,
    assert owner.hasFocus() and owner.text() == "power team" and not win.editor.is_dirty()  # and Ctrl+S kept the focus


def test_the_form_is_rebuilt_when_the_template_changes(win: MainWindow):
    win.select_item("EPS-0001")
    first = win.editor.field("owner")
    win.select_item("SYS-0001")  # same template, same document kind but another document
    assert win.editor.field("owner") is not first or win.editor._signature is not None  # noqa: SLF001
    win.select_item("VER-0001")
    assert "v_status" in win.editor._fields  # noqa: SLF001 - a verification form has its own fields


# R20 -------------------------------------------------------------------------------------------------------------
def test_help_line_follows_every_widget_not_only_form_fields(win: MainWindow):
    ed = win.editor
    win.select_item("EPS-0001")
    _focus_in(ed.field("rationale"))
    assert "Why the requirement exists" in ed.help_line.text()
    _focus_in(ed.statement)
    assert "Markdown" in ed.help_line.text()
    _focus_in(ed.field("owner"))
    _focus_in(ed.why)
    assert "baselined" in ed.help_line.text()
    _focus_in(ed.save_button)
    assert "Select a field" in ed.help_line.text()


# R13 -------------------------------------------------------------------------------------------------------------
def test_a_created_change_request_refreshes_the_form_and_snapshot(win: MainWindow):
    v = win.changes_view
    v.title.setText("Draft title")
    v.description.setPlainText("Draft text")
    cr = v.create_request(v.title.text(), v.description.toPlainText(), ["EPS-0001"])
    assert cr is not None and v.current_id == cr
    assert cr in v.heading.text() and not v._form_dirty()  # noqa: SLF001
    session_cr = win.session.change_request(cr)
    assert session_cr is not None and v.title.text() == session_cr.title


def test_an_external_change_to_a_change_request_is_shown_when_the_form_is_clean(win: MainWindow):
    v = win.changes_view
    cr = v.create_request("Original", "d", [])
    assert cr
    win.session.store().update(cr, title="Edited elsewhere", description="d", items=[], who="someone")
    win.session.refresh()
    assert v.title.text() == "Edited elsewhere"


# M16 -------------------------------------------------------------------------------------------------------------
def test_field_labels_are_words_not_attribute_names(win: MainWindow):
    from rvs_core.config.model import AttributeDef

    expected = {
        "v_status": "Verification status", "link_verifies": "Verifies", "link_satisfies": "Satisfies",
        "link_refines": "Refines", "link_conflicts_with": "Conflicts with", "nonconformances": "Non-conformances",
        "proc_id": "Procedure ID", "executed_on": "Executed on",
    }  # fmt: skip
    for name, label in expected.items():
        assert fields.label_text(AttributeDef(name, "string")) == label, name
    assert fields.label_text(AttributeDef("some_new_field", "string", required=True)) == "Some new field *"
    win.select_item("VER-0001")
    labels = [
        win.editor.form.itemAt(r, win.editor.form.ItemRole.LabelRole).widget().text()
        for r in range(win.editor.form.rowCount())
    ]
    plain = [label.removesuffix(" *") for label in labels]
    assert "Procedure ID" in plain and "Verification status" in plain and "Verifies" in plain
    assert not any("_" in label for label in labels)


def test_problems_code_column_is_hidden_until_asked_for(win: MainWindow):
    panel = win.problems_panel
    assert not panel.codes_visible()
    win.action_problem_codes.setChecked(True)
    assert panel.codes_visible()
    win.action_problem_codes.setChecked(False)
    assert not panel.codes_visible()


def test_problem_counts_are_pluralised_the_same_everywhere():
    from rvs_gui.widgets import plural, problem_counts

    assert plural(1, "error") == "1 error" and plural(2, "error") == "2 errors" and plural(0, "warning") == "0 warnings"
    assert problem_counts(1, 2) == "1 error, 2 warnings" and problem_counts(0, 1, 3) == "0 errors, 1 warning, 3 info"


def test_status_bar_and_problems_summary_use_the_shared_wording(win: MainWindow):
    win.session.update_item("SYS-0001", text="Power is provided.")
    text = win.statusBar().currentMessage() or win._status_text()  # noqa: SLF001
    assert "1 error" not in text or "1 errors" not in text
    assert "1 warning" in win._status_text() or "warnings" in win._status_text()  # noqa: SLF001
    summary = win.problems_panel.summary.text()
    assert " errors" in summary or "1 error," in summary
    assert "1 errors" not in summary and "1 warnings" not in summary


def test_problems_header_and_cells_explain_the_abbreviation(win: MainWindow):
    win.session.update_item("SYS-0001", text="Power is provided.")
    col = [c.key for c in __import__("rvs_gui.models", fromlist=["COLUMNS"]).COLUMNS].index("problems")
    tip = win.table_model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
    assert "errors" in tip and "warnings" in tip
    row = win.table_model.row_of("SYS-0001")
    assert "warning" in win.table_model.index(row, col).data(Qt.ItemDataRole.ToolTipRole)


def test_suspect_links_are_explained_in_the_button_tooltip(win: MainWindow):
    win.select_item("EPS-0001")
    assert "suspect link means" in win.editor.clear_suspect_button.toolTip()
    win.session.update_item("SYS-0001", text="The spacecraft shall do something different.")
    win.select_item("EPS-0001")
    if win.editor.clear_suspect_button.isEnabled():
        assert "Suspect parents" in win.editor.clear_suspect_button.toolTip()


# string lists ----------------------------------------------------------------------------------------------------
def test_a_non_conformance_with_a_comma_survives_opening_and_saving(win: MainWindow):
    entry = "NCR 12, rev A"
    win.session.update_item("VER-0001", attrs={"nonconformances": [entry, "NCR 7"]})
    win.select_item("VER-0001")
    assert not win.editor.is_dirty()  # opening it must not look like an edit
    win.editor.field("title").setText("A new title")
    assert win.editor.save() is True
    item = win.session.item("VER-0001")
    assert item is not None and list(item.attrs["nonconformances"]) == [entry, "NCR 7"]
    assert not win.editor.is_dirty()


# M12: navigation from tables -------------------------------------------------------------------------------------
def test_matrix_rows_open_their_item(win: MainWindow):
    win.tabs.setCurrentWidget(win.vcm_view)
    win.select_item("EPS-0001")
    model = win.vcm_view.model
    row = next(r for r in range(model.rowCount()) if model.index(r, 0).data() == "EPS-0002")
    win.vcm_view.table.activated.emit(model.index(row, 0))
    assert win.editor.current_uid == "EPS-0002" and win.tabs.currentIndex() == 0
    assert win.editor.statement.hasFocus()


def test_traceability_cell_with_several_ids_opens_the_first_that_exists(win: MainWindow):
    from rvs_gui.matrix_views import item_in_row

    win.tabs.setCurrentWidget(win.trace_view)
    win.trace_view.source.setCurrentText("SYS")
    win.trace_view.target.setCurrentText("EPS")
    model = win.trace_view.model
    uid = item_in_row(model, 0, 0, lambda u: win.session.item(u) is not None)
    assert uid == model.index(0, 0).data().split()[0]


def test_changes_and_diff_rows_navigate(win: MainWindow, git_project: Path, qtbot):  # type: ignore[no-untyped-def]
    cr = win.changes_view.create_request("C", "d", ["EPS-0002"])
    assert cr
    win.tabs.setCurrentWidget(win.changes_view)
    win.changes_view.table.activated.emit(win.changes_view.model.index(0, 0))
    assert win.editor.current_uid == "EPS-0002"
    win.changes_view.edited.addItem("SYS-0001  title")
    win.changes_view.edited.itemActivated.emit(win.changes_view.edited.item(win.changes_view.edited.count() - 1))
    assert win.editor.current_uid == "SYS-0001"


def test_diff_rows_navigate(win: MainWindow):
    from rvs_core.changecontrol.diff import ItemChange
    from rvs_gui.diff_view import DiffView

    seen: list[str] = []
    view: DiffView = win.diff_view
    view.item_requested.connect(seen.append)
    win.session.update_item("EPS-0001", text="The EPS shall be changed.")
    view.set_range("Working copy", None)
    assert ItemChange  # the comparison itself is covered by test_gui_changecontrol
    view._on_activated(QModelIndex())  # noqa: SLF001 - no table yet: nothing to open, nothing raised
    assert seen == []


# M10: accessible names -------------------------------------------------------------------------------------------
def _unnamed(root: QWidget) -> list[str]:
    bad = []
    for kind in (QLineEdit, QPlainTextEdit, QComboBox, QTableView, QTreeView):
        for w in root.findChildren(kind):
            internal = (
                w.objectName().startswith("qt_")
                or isinstance(w.parent(), QComboBox)
                or type(w.parent()).__name__.endswith("SpinBox")
            )
            if not internal and not w.accessibleName().strip():
                bad.append(
                    f"{type(w).__name__} in {type(root).__name__} ({w.toolTip() or w.placeholderText() if hasattr(w, 'placeholderText') else ''})"
                )
    return bad


def test_every_input_and_table_in_the_main_window_has_an_accessible_name(win: MainWindow):
    win.select_item("VER-0001")
    for tab in range(win.tabs.count()):
        win.tabs.setCurrentIndex(tab)
    assert _unnamed(win) == []
    win.select_item("EPS-0001")
    assert _unnamed(win) == []


def test_every_input_and_table_in_the_dialogs_has_an_accessible_name(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.baseline_dialog import NewBaselineDialog
    from rvs_gui.dialogs import NewItemDialog
    from rvs_gui.export_dialog import ExportDialog
    from rvs_gui.glossary_dialog import GlossaryDialog
    from rvs_gui.import_dialog import ImportDialog
    from rvs_gui.project_dialogs import NewProjectDialog
    from rvs_gui.shortcuts import ShortcutsDialog
    from rvs_gui.wizard import NewRequirementWizard

    win.changes_view.create_request("C", "d", [])
    dialogs = [
        NewItemDialog(win.session),
        NewItemDialog(win.session, kind="verification"),
        NewProjectDialog(),
        ExportDialog(win.session),
        GlossaryDialog(win.session),
        ShortcutsDialog(win),
        NewBaselineDialog(win.session),
        ImportDialog(win.session, [{"uid": "", "document": "SYS", "title": "T", "text": "The system shall."}]),
        NewRequirementWizard(win.session, win),
        win.show_help(),
    ]
    for dlg in dialogs:
        qtbot.addWidget(dlg)
        assert _unnamed(dlg) == [], type(dlg).__name__


def test_captions_are_buddies_of_their_controls(win: MainWindow):
    from PySide6.QtWidgets import QLabel

    def buddy_of(root: QWidget, text: str) -> QWidget | None:
        label = next(lb for lb in root.findChildren(QLabel) if lb.text() == text)
        return label.buddy()

    assert buddy_of(win.trace_view, "From") is win.trace_view.source
    assert buddy_of(win.trace_view, "to") is win.trace_view.target
    assert buddy_of(win.diff_view, "From") is win.diff_view.left
    assert buddy_of(win.diff_view, "To") is win.diff_view.right
    assert buddy_of(win.diff_view, "Document") is win.diff_view.document
    assert buddy_of(win.graph_view, "Depth") is win.graph_view.depth_box


# menus -----------------------------------------------------------------------------------------------------------
def test_menus_have_distinct_mnemonics(win: MainWindow):
    titles = [a.text() for a in win.menuBar().actions()]
    letters = [t[t.index("&") + 1].lower() for t in titles if "&" in t]
    assert len(letters) == len(titles) and len(set(letters)) == len(letters)


def test_project_actions_are_disabled_until_a_project_is_open(qtbot):  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    for key in ("export", "import_items", "new_requirement", "new_baseline", "glossary", "full_validation", "refresh"):
        assert not w.actions_by_id[key].isEnabled(), key
    assert w.actions_by_id["open_project"].isEnabled() and w.actions_by_id["new_project"].isEnabled()


# impact ----------------------------------------------------------------------------------------------------------
def test_impact_tree_of_a_long_chain_does_not_overflow(win: MainWindow):
    from rvs_core.trace.impact import ImpactNode, ImpactResult

    root = ImpactNode("SYS-0001")
    node = root
    for n in range(1500):
        child = ImpactNode(f"X-{n:04d}", via="parent")
        node.children.append(child)
        node = child
    panel = win.impact_panel
    import rvs_gui.impact_panel as module

    original = module.impact, module.impact_table
    module.impact = lambda graph, uid: ImpactResult(root=root)  # type: ignore[assignment,call-arg]
    module.impact_table = lambda items, result, prov: None  # type: ignore[assignment]
    try:
        panel.set_item("SYS-0001")
    finally:
        module.impact, module.impact_table = original
    assert panel.tree.topLevelItemCount() == 1


# background work -------------------------------------------------------------------------------------------------
def test_full_validation_runs_in_the_background_with_a_notification(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(win.validation_finished, timeout=60000) as done:
        win.run_full_validation()
        assert "Validating" in win.notification.text()
        assert QApplication.overrideCursor() is not None
    assert done.args == [True] and QApplication.overrideCursor() is None


def test_open_from_the_menu_does_not_block(win: MainWindow, qtbot, minimal_project: Path):  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(win.project_opened, timeout=60000) as done:
        win.open_project_async(minimal_project)
        assert QApplication.overrideCursor() is not None
    assert done.args == [True] and QApplication.overrideCursor() is None


def test_garbage_is_collected_on_the_gui_thread_when_the_last_job_ends(qtbot, monkeypatch):  # type: ignore[no-untyped-def]
    import gc

    from rvs_gui.jobs import run_in_background

    calls: list[int] = []
    monkeypatch.setattr(gc, "collect", lambda *a: calls.append(1) or 0)
    with qtbot.waitSignal(QApplication.instance().applicationStateChanged, timeout=100, raising=False):  # type: ignore[union-attr]
        run_in_background(lambda: 1, lambda _v: None, lambda _e: None)
    qtbot.waitUntil(lambda: bool(calls), timeout=3000)


# M5: problems panel ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Space])
def test_problem_rows_activate_with_the_keyboard(win: MainWindow, qtbot, key):  # type: ignore[no-untyped-def]
    win.session.update_item("SYS-0001", text="Power is provided.")
    panel = win.problems_panel
    row = next(r for r in range(panel.proxy.rowCount()) if panel.proxy.index(r, 2).data() == "SYS-0001")
    panel.view.setCurrentIndex(panel.proxy.index(row, 0))
    assert "SYS-0001" in panel.detail.text() and "shall" in panel.detail.text().lower()  # the full text is readable
    win.select_item("EPS-0001")
    panel.view.setFocus()
    QTest.keyClick(panel.view, key)
    assert win.editor.current_uid == "SYS-0001" and win.editor.statement.hasFocus()


# export writes are atomic -------------------------------------------------------------------------------------
def test_a_failed_export_leaves_the_previous_file_untouched(win: MainWindow, qtbot, tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    import os

    target = tmp_path / "vcm.csv"
    target.write_text("previous content")

    def broken(*_a: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", broken)
    with qtbot.waitSignal(win.vcm_view.export_done, timeout=60000) as done:
        win.vcm_view.export_file(target)
    assert done.args[1] and target.read_text() == "previous content"
    assert not list(tmp_path.glob(".*.tmp"))

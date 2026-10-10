"""GUI audit B1/B2: no keyboard traps, a sensible tab order, focus follows navigation."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication, QPlainTextEdit, QWidget

from rvs_gui.app import MainWindow, create_main_window
from rvs_gui.shortcuts import SHORTCUTS


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


def _walk(root: QWidget, kind: type) -> list:  # type: ignore[type-arg]
    return [root, *root.findChildren(QWidget)] if isinstance(root, kind) else root.findChildren(kind)


def test_no_table_or_tree_in_the_main_window_traps_the_tab_key(win: MainWindow):
    views = win.findChildren(QAbstractItemView)
    assert len(views) >= 8
    trapped = [v.accessibleName() or v.objectName() or type(v).__name__ for v in views if v.tabKeyNavigation()]
    assert not trapped, trapped


def test_dialog_tables_do_not_trap_the_tab_key(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.baseline_dialog import NewBaselineDialog
    from rvs_gui.glossary_dialog import GlossaryDialog
    from rvs_gui.shortcuts import ShortcutsDialog

    for dlg in (GlossaryDialog(win.session), ShortcutsDialog(win), NewBaselineDialog(win.session)):
        qtbot.addWidget(dlg)
        for view in dlg.findChildren(QAbstractItemView):
            assert not view.tabKeyNavigation(), (type(dlg).__name__, view.accessibleName())


def test_multi_line_fields_let_tab_move_on(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.wizard import NewRequirementWizard

    win.select_item("EPS-0001")
    boxes = win.editor.findChildren(QPlainTextEdit)
    assert win.editor.statement in boxes and win.editor.field("rationale") in boxes
    assert all(b.tabChangesFocus() for b in boxes)
    assert all(b.tabChangesFocus() for b in win.changes_view.findChildren(QPlainTextEdit))
    wizard = NewRequirementWizard(win.session, win)
    qtbot.addWidget(wizard)
    assert all(b.tabChangesFocus() for b in wizard.findChildren(QPlainTextEdit))


def test_tab_from_the_statement_reaches_the_reason_and_buttons(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.select_item("EPS-0001")
    ed = win.editor
    ed.statement.setPlainText("The EPS shall do something else.")
    ed.statement.setFocus()
    QTest.keyClick(ed.statement, Qt.Key.Key_Tab)
    assert ed.why.hasFocus()
    assert ed.statement.toPlainText() == "The EPS shall do something else."  # no tab character was typed


def test_tab_order_runs_search_status_checkbox_table_then_editor(win: MainWindow):
    bar = win.filter_bar
    win.select_item("EPS-0001")
    order = [bar.search, bar.status, bar.only_problems, win.table, *win.editor.focus_chain()]
    seen = [bar.search]
    widget = bar.search
    for _ in range(len(order) - 1):
        widget = widget.nextInFocusChain()
        while widget not in order:  # skip children such as the clear button or the combo's line edit
            widget = widget.nextInFocusChain()
        seen.append(widget)
    assert seen == order


def test_a_focus_editor_shortcut_exists_and_works(win: MainWindow):
    key = SHORTCUTS["focus_editor"][0]
    assert [k for k, _d in SHORTCUTS.values()].count(key) == 1  # no collision
    assert win.actions_by_id["focus_editor"].shortcut() == QKeySequence(key)
    win.select_item("EPS-0001")
    win.filter_bar.search.setFocus()
    win.actions_by_id["focus_editor"].trigger()
    assert win.editor.statement.hasFocus()


def test_enter_on_an_item_row_moves_focus_to_the_editor(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.select_item("EPS-0001")
    win.table.setFocus()
    qtbot.waitUntil(win.table.hasFocus, timeout=2000)
    QTest.keyClick(win.table, Qt.Key.Key_Return)
    assert win.editor.statement.hasFocus()


def test_go_to_and_next_problem_put_the_focus_in_the_editor(win: MainWindow):
    win.session.update_item("SYS-0001", text="Power is provided.")
    win.filter_bar.search.setFocus()
    assert win.go_to("eps-0002")
    assert win.editor.current_uid == "EPS-0002" and win.editor.statement.hasFocus()
    win.table.setFocus()
    assert win.next_problem() is not None
    assert win.editor.statement.hasFocus()


def test_the_import_dialog_table_reason_and_import_button_are_reachable_by_tab(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.import_dialog import ImportDialog

    rows = [{"uid": "", "document": "SYS", "title": "New", "text": "The system shall be new."}]
    dlg = ImportDialog(win.session, rows)
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.activateWindow()
    qtbot.waitUntil(dlg.isActiveWindow, timeout=3000)
    dlg.table.setFocus()
    QTest.keyClick(dlg.table, Qt.Key.Key_Tab)
    assert dlg.reason.hasFocus()
    QTest.keyClick(dlg.reason, Qt.Key.Key_Tab)
    assert dlg.skip_errors.hasFocus()
    QTest.keyClick(dlg.skip_errors, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() in (dlg.apply_button, dlg.buttons.button(dlg.buttons.StandardButton.Cancel))


def test_escape_clears_the_search_then_dismisses_the_notification(win: MainWindow):
    win.filter_bar.search.setText("power")
    win.filter_bar.search.setFocus()
    QTest.keyClick(win.filter_bar.search, Qt.Key.Key_Escape)
    assert win.filter_bar.search.text() == ""
    win.notification.show_message("warning", "Careful")
    assert win.notification.isVisible()
    QTest.keyClick(win.table, Qt.Key.Key_Escape)
    assert not win.notification.isVisible()

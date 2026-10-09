"""Editor layout: help for the field being edited (not under every field), and enough fields visible at once."""

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from rvs_gui.app import MainWindow, create_main_window


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.resize(1400, 960)
    w.show()
    assert w.open_project(minimal_project)
    w.select_item("EPS-0001")
    return w


def _focus(widget) -> None:  # type: ignore[no-untyped-def]
    QApplication.sendEvent(widget, QFocusEvent(QEvent.Type.FocusIn))


def test_help_line_follows_the_field_being_edited(win: MainWindow):
    editor = win.editor
    assert "Select a field" in editor.help_line.text()
    _focus(editor.field("rationale"))
    assert "Why the requirement exists" in editor.help_line.text()
    _focus(editor.field("parents"))
    assert "derives from" in editor.help_line.text()
    _focus(editor.field("verify_method"))
    assert "How compliance will be shown" in editor.help_line.text()


def test_help_line_is_a_guided_mode_feature(win: MainWindow):
    assert win.editor.help_line.isVisibleTo(win.editor)
    win.set_mode("expert")
    assert not win.editor.help_line.isVisibleTo(win.editor) and win.editor.help_visible() is False
    win.set_mode("guided")
    assert win.editor.help_line.isVisibleTo(win.editor)


def test_the_form_has_one_row_per_field_no_help_rows(win: MainWindow):
    editor = win.editor
    assert editor.form.rowCount() == len(editor._defs) + 1  # noqa: SLF001 - every attribute plus Parents


def test_most_fields_are_visible_without_scrolling_on_a_normal_screen(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    qtbot.wait(100)
    editor = win.editor
    scroll = editor.form_scroll
    viewport = scroll.viewport()
    visible = 0
    for widget in editor._fields.values():  # noqa: SLF001
        top = widget.mapTo(viewport, widget.rect().topLeft()).y()
        if top >= 0 and top + widget.height() <= viewport.height():
            visible += 1
    assert visible >= 8, f"only {visible} of {len(editor._fields)} fields fit"  # noqa: SLF001


def test_statement_and_problems_keep_a_usable_size(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    qtbot.wait(100)
    statement = win.editor.statement
    assert isinstance(statement, QPlainTextEdit)
    assert statement.height() >= 90 and win.editor.item_findings.height() <= 80

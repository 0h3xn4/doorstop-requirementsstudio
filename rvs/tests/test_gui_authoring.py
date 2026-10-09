"""pytest-qt tests for the M2 flows: open, browse, filter, edit, save, create, problems, jump."""

import shutil
from pathlib import Path

import pytest
import yaml
from PySide6.QtCore import Qt

from conftest import EXAMPLES
from rvs_core.authoring import read_history
from rvs_gui.app import MainWindow, create_main_window
from rvs_gui.models import COLUMNS


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    w.open_project(minimal_project)
    return w


@pytest.fixture
def sat_win(qtbot, tmp_path: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    root = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "satellite300", root)
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    w.open_project(root)
    return w


def _select(win: MainWindow, uid: str) -> None:
    assert win.select_item(uid), uid


# open / browse ---------------------------------------------------------------------
def test_open_populates_tree_and_table(win: MainWindow):
    assert win.table_model.rowCount() == 10
    assert win.doc_tree.document_prefixes() == ["SYS", "EPS", "VER"]
    assert win.doc_tree.item_uids("EPS") == ["EPS-0001", "EPS-0002", "EPS-0003"]
    assert "Minimal example" in win.windowTitle()


def test_open_invalid_project_shows_friendly_error_not_traceback(qtbot, tmp_path: Path, minimal_project: Path):  # type: ignore[no-untyped-def]
    p = minimal_project / "rvs-project.yaml"
    data = yaml.safe_load(p.read_text())
    data["rvs_schema_version"] = 99
    p.write_text(yaml.safe_dump(data))
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project) is False
    text = w.notification.text()
    assert "99" in text and "newer" in text.lower() and "Traceback" not in text
    assert w.notification.kind == "error"


def test_tree_selection_filters_table_and_item_selection_opens_editor(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.doc_tree.select_document("EPS")
    assert win.table_proxy.rowCount() == 3
    win.doc_tree.select_document(None)
    assert win.table_proxy.rowCount() == 10
    win.doc_tree.select_item("EPS-0002")
    assert win.editor.current_uid == "EPS-0002"


def test_table_text_filter_and_status_filter(win: MainWindow):
    win.filter_bar.search.setText("battery")
    assert win.table_proxy.rowCount() == 1
    win.filter_bar.search.setText("")
    idx = win.filter_bar.status.findText("approved")
    win.filter_bar.status.setCurrentIndex(idx)
    assert win.table_proxy.rowCount() == 0
    win.filter_bar.status.setCurrentIndex(0)
    assert win.table_proxy.rowCount() == 10


def test_table_sorting_by_column(win: MainWindow):
    col = [c.key for c in COLUMNS].index("title")
    win.table.sortByColumn(col, Qt.SortOrder.DescendingOrder)
    titles = [win.table_proxy.index(r, col).data() for r in range(win.table_proxy.rowCount())]
    assert titles == sorted(titles, reverse=True)


def test_column_chooser_hides_and_shows_columns(win: MainWindow):
    col = [c.key for c in COLUMNS].index("owner")
    win.set_column_visible("owner", False)
    assert win.table.isColumnHidden(col)
    win.set_column_visible("owner", True)
    assert not win.table.isColumnHidden(col)


# editor ---------------------------------------------------------------------------
def test_editor_shows_fields_and_live_markdown_preview(win: MainWindow):
    _select(win, "SYS-0001")
    ed = win.editor
    assert ed.field("title").text() == "Payload power"
    assert ed.field("status").currentText() == "draft"
    assert "shall provide electrical power" in ed.statement.toPlainText()
    ed.statement.setPlainText("The spacecraft **shall** provide power.")
    assert "shall" in ed.preview.toPlainText() and "**" not in ed.preview.toPlainText()
    assert ed.is_dirty()


def test_edit_save_flow_writes_item_history_and_refreshes(win: MainWindow):
    _select(win, "SYS-0001")
    ed = win.editor
    ed.field("title").setText("Payload power supply")
    ed.statement.setPlainText("The spacecraft shall provide electrical power to every payload.")
    ed.why.setText("clarify scope")
    assert ed.save() is True
    assert not ed.is_dirty()
    root = win.session.root
    assert root is not None
    assert "Payload power supply" in (root / "SYS" / "SYS-0001.yml").read_text()
    (entry,) = read_history(root, "SYS-0001")
    assert entry["why"] == "clarify scope" and entry["fields"] == ["text", "title"]
    row_title = win.table_model.index(
        win.table_model.row_of("SYS-0001"), [c.key for c in COLUMNS].index("title")
    ).data()
    assert row_title == "Payload power supply"
    assert win.notification.kind == "success"


def test_revert_restores_saved_values(win: MainWindow):
    _select(win, "SYS-0001")
    win.editor.field("title").setText("changed")
    assert win.editor.is_dirty()
    win.editor.revert()
    assert win.editor.field("title").text() == "Payload power" and not win.editor.is_dirty()


def test_baselined_item_requires_a_reason(win: MainWindow):
    win.session.update_item("SYS-0001", attrs={"status": "baselined"})
    _select(win, "SYS-0001")
    before = (win.session.root / "SYS" / "SYS-0001.yml").read_bytes()  # type: ignore[operator]
    win.editor.field("owner").setText("somebody")
    assert win.editor.save() is False
    assert win.notification.kind == "error" and "reason" in win.notification.text().lower()
    assert (win.session.root / "SYS" / "SYS-0001.yml").read_bytes() == before  # type: ignore[operator]
    win.editor.why.setText("customer request")
    assert win.editor.save() is True


def test_switching_item_with_unsaved_changes_is_blocked_with_a_message(win: MainWindow):
    _select(win, "SYS-0001")
    win.editor.field("title").setText("dirty")
    assert win.select_item("SYS-0002") is False
    assert win.editor.current_uid == "SYS-0001"
    assert win.notification.kind == "warning" and "save" in win.notification.text().lower()
    win.editor.revert()
    assert win.select_item("SYS-0002") is True


def test_invalid_parent_is_reported_inline(win: MainWindow):
    _select(win, "EPS-0001")
    win.editor.field("parents").setText("SYS-0099")
    assert win.editor.save() is False
    assert "SYS-0099" in win.notification.text() and win.notification.kind == "error"


def test_editor_shows_findings_for_the_current_item(win: MainWindow):
    win.session.update_item("SYS-0001", text="Power is provided.")
    _select(win, "SYS-0001")
    texts = [win.editor.item_findings.item(i).text() for i in range(win.editor.item_findings.count())]
    assert any("shall" in t for t in texts)


def test_undefined_acronyms_are_highlighted(win: MainWindow):
    _select(win, "SYS-0001")
    win.editor.statement.setPlainText("The OBC shall use the EPS and TT&C.")
    spans = win.editor.highlighter.undefined_spans()
    assert [win.editor.statement.toPlainText()[a:b] for a, b in spans] == ["OBC", "TT&C"]  # EPS is defined


# create -----------------------------------------------------------------------------
def test_create_requirement_flow(win: MainWindow):
    uid = win.create_item("EPS", "Charge control", parents=["SYS-0002"])
    assert uid == "EPS-0004"
    assert win.table_model.rowCount() == 11
    assert win.editor.current_uid == uid
    assert "shall" in win.editor.statement.toPlainText()  # template text is a valid starting point
    assert win.doc_tree.item_uids("EPS")[-1] == uid
    assert not [f for f in win.session.findings_for(uid) if f.code == "RVS-RULE-HAS-PARENT"]


def test_new_item_dialog_returns_choices(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.dialogs import NewItemDialog

    dlg = NewItemDialog(win.session)
    qtbot.addWidget(dlg)
    assert dlg.documents() == ["SYS", "EPS"]  # requirements documents only
    dlg.document.setCurrentText("EPS")
    dlg.title.setText("Thing")
    dlg.parents.setText("SYS-0001, SYS-0002")
    assert dlg.values() == ("EPS", "Thing", ["SYS-0001", "SYS-0002"])


# problems panel ---------------------------------------------------------------------
def test_problems_panel_lists_findings_sorted_by_severity(sat_win: MainWindow):
    panel = sat_win.problems_panel
    sevs = [panel.model_.index(r, 0).data(Qt.ItemDataRole.UserRole) for r in range(panel.proxy.rowCount())]
    assert sevs and sevs == sorted(sevs)  # errors (0) first
    assert "errors" in panel.summary.text() and "warnings" in panel.summary.text()


def test_problem_double_click_jumps_to_item(sat_win: MainWindow):
    panel = sat_win.problems_panel
    row = next(r for r in range(panel.proxy.rowCount()) if panel.proxy.index(r, 2).data() == "EPS-0001")
    panel.view.doubleClicked.emit(panel.proxy.index(row, 0))
    assert sat_win.editor.current_uid == "EPS-0001"
    assert sat_win.table.currentIndex().data() is not None


def test_problems_update_after_fixing_an_item(sat_win: MainWindow):
    _select(sat_win, "EPS-0001")
    sat_win.editor.statement.setPlainText("The EPS shall provide a regulated 28 V main bus.")
    assert sat_win.editor.save() is True
    assert not [f for f in sat_win.session.findings if f.uid == "EPS-0001" and f.code == "RVS-RULE-SHALL-PRESENT"]


def test_problems_panel_filters_to_severity(sat_win: MainWindow):
    panel = sat_win.problems_panel
    total = panel.proxy.rowCount()
    panel.show_errors_only(True)
    assert 0 < panel.proxy.rowCount() < total
    assert all(panel.proxy.index(r, 0).data(Qt.ItemDataRole.UserRole) == 0 for r in range(panel.proxy.rowCount()))

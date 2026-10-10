"""pytest-qt tests for M5: change requests, baselines, diff view."""

from pathlib import Path

import pytest

from rvs_core.authoring import EditService, read_history
from rvs_core.changecontrol.baselines import list_baselines
from rvs_gui.app import MainWindow, create_main_window


@pytest.fixture
def win(qtbot, git_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(git_project)
    return w


def _col(model, col: int = 0) -> list[str]:  # type: ignore[no-untyped-def]
    return [model.index(r, col).data() for r in range(model.rowCount())]


def test_tabs_include_change_control(win: MainWindow):
    names = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert names[-3:] == ["Changes", "Baselines", "Diff"]


# change requests -----------------------------------------------------------------------------------------
def test_create_and_edit_a_change_request(win: MainWindow):
    v = win.changes_view
    cr_id = v.create_request("Change the bus", "28 V", ["EPS-0001"])
    assert cr_id == "CR-0001" and _col(v.model) == ["CR-0001"]
    assert v.model.index(0, 1).data() == "open"
    v.select(cr_id)
    v.status.setCurrentText("in-review")
    v.title.setText("Change the bus voltage")
    v.save()
    assert win.session.change_request(cr_id).status == "in-review"  # type: ignore[union-attr]
    assert v.model.index(0, 2).data() == "Change the bus voltage"
    assert win.notification.kind == "success"


def test_edits_under_an_active_change_request_are_attributed(win: MainWindow):
    v = win.changes_view
    cr_id = v.create_request("T", "", [])
    v.select(cr_id)
    v.use_for_edits.setChecked(True)
    assert win.session.active_cr == cr_id and cr_id in win.statusBar().currentMessage()
    win.select_item("SYS-0001")
    win.editor.field("owner").setText("power")
    win.editor.why.setText("because")
    assert win.editor.save()
    assert read_history(win.session.root, "SYS-0001")[-1]["cr"] == cr_id  # type: ignore[arg-type]
    assert v.edited.count() == 1 and "SYS-0001" in v.edited.item(0).text()


def test_a_closed_change_request_cannot_be_used_for_edits(win: MainWindow):
    v = win.changes_view
    cr_id = v.create_request("T", "", [])
    v.select(cr_id)
    v.status.setCurrentText("closed")
    v.save()
    v.use_for_edits.setChecked(True)
    assert win.session.active_cr is None and win.notification.kind == "error" and "closed" in win.notification.text()


# baselines -------------------------------------------------------------------------------------------------------
def test_create_baseline_in_the_background_and_list_it(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000) as sig:
        win.baselines_view.create_baseline("PDR", "Preliminary design review", {})
    assert sig.args == ["PDR", ""]
    assert _col(win.baselines_view.model) == ["PDR"]
    assert win.baselines_view.model.index(0, 3).data() == "10"
    assert win.notification.kind == "success" and "PDR" in win.notification.text()
    assert [b.name for b in list_baselines(win.session.root)] == ["PDR"]  # type: ignore[arg-type]


def test_baseline_dialog_lists_open_change_requests_and_blocks_until_deferred(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.baseline_dialog import NewBaselineDialog

    win.changes_view.create_request("Pending", "", [])
    dlg = NewBaselineDialog(win.session)
    qtbot.addWidget(dlg)
    dlg.name.setText("PDR")
    dlg.description.setText("d")
    assert dlg.open_list.count() == 1 and not dlg.create_button.isEnabled()
    assert "CR-0001" in dlg.problem.text()
    dlg.defer_checkbox(0).setChecked(True)
    assert not dlg.create_button.isEnabled()  # a reason is needed
    dlg.defer_reason(0).setText("after PDR")
    assert dlg.create_button.isEnabled()
    assert dlg.values() == ("PDR", "d", {"CR-0001": "after PDR"})


def test_baseline_dialog_validates_the_name(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.baseline_dialog import NewBaselineDialog

    dlg = NewBaselineDialog(win.session)
    qtbot.addWidget(dlg)
    dlg.name.setText("bad name")
    dlg.description.setText("d")
    assert not dlg.create_button.isEnabled() and "name" in dlg.problem.text().lower()
    dlg.name.setText("PDR-1")
    assert dlg.create_button.isEnabled()


def test_baseline_with_open_change_requests_fails_with_a_message(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.changes_view.create_request("Pending", "", [])
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000) as sig:
        win.baselines_view.create_baseline("PDR", "d", {})
    assert sig.args[1] and win.notification.kind == "error" and "CR-0001" in win.notification.text()


def test_baseline_promotes_status_and_the_table_updates(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.session.update_item("SYS-0001", attrs={"status": "approved"})
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000):
        win.baselines_view.create_baseline("PDR", "d", {})
    assert win.session.item("SYS-0001").attrs["status"] == "baselined"  # type: ignore[union-attr]


def test_editing_a_baselined_item_needs_a_reason_in_the_gui(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000):
        win.baselines_view.create_baseline("PDR", "d", {})
    win.select_item("SYS-0001")
    win.editor.field("owner").setText("x")
    assert win.editor.save() is False and "reason" in win.notification.text().lower()
    win.editor.why.setText("customer request")
    assert win.editor.save() is True


def test_verify_button_reports(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000):
        win.baselines_view.create_baseline("PDR", "d", {})
    win.baselines_view.select("PDR")
    win.baselines_view.verify()
    assert win.notification.kind == "success" and "intact" in win.notification.text()
    manifest = win.session.root / "baselines" / "PDR.yaml"  # type: ignore[operator]
    manifest.write_text(manifest.read_text() + "# x\n")
    win.baselines_view.verify()
    assert win.notification.kind == "error" and "changed" in win.notification.text()


def test_outputs_carry_the_latest_baseline_in_their_provenance(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.tabs.setCurrentWidget(win.vcm_view)
    assert "no baseline" in win.vcm_view.provenance_label.text()
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000):
        win.baselines_view.create_baseline("PDR", "d", {})
    assert "latest baseline: PDR" in win.vcm_view.provenance_label.text()


# diff view ----------------------------------------------------------------------------------------------------------
def _baseline(win: MainWindow, qtbot, name: str = "PDR") -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(win.baselines_view.baseline_done, timeout=60000):
        win.baselines_view.create_baseline(name, "d", {})


def test_diff_view_lists_changes_and_shows_marked_text(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    _baseline(win, qtbot)
    win.session.update_item(
        "SYS-0001", text="The spacecraft shall provide regulated power.", attrs={"owner": "z"}, why="x"
    )
    v = win.diff_view
    v.left.setCurrentText("PDR")
    v.right.setCurrentText("Working copy")
    with qtbot.waitSignal(v.diff_ready, timeout=60000):
        v.compare()
    assert _col(v.model) == ["SYS-0001"] and v.model.index(0, 1).data() == "changed"
    assert "1 changed" in v.summary.text()
    v.select_row(0)
    html = v.detail.toHtml()
    assert "regulated" in html and "electrical" in html  # both versions are shown, marked
    assert "line-through" in html  # deleted words struck through


def test_diff_view_shows_added_and_removed_items(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    _baseline(win, qtbot)
    win.session.create_item(
        "EPS", "The EPS shall be new.", attrs={"title": "New", "type": "functional"}, parents=["SYS-0001"]
    )
    v = win.diff_view
    v.left.setCurrentText("PDR")
    v.right.setCurrentText("Working copy")
    with qtbot.waitSignal(v.diff_ready, timeout=60000):
        v.compare()
    assert _col(v.model) == ["EPS-0004"] and v.model.index(0, 1).data() == "added"


def test_diff_view_between_two_baselines_and_document_filter(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    _baseline(win, qtbot, "A")
    EditService(win.session.root, user="b").update_item("SYS-0001", attrs={"owner": "a"}, why="x")  # type: ignore[arg-type]
    EditService(win.session.root, user="b").update_item("EPS-0001", attrs={"owner": "b"}, why="x")  # type: ignore[arg-type]
    win.session.refresh()
    _baseline(win, qtbot, "B")
    v = win.diff_view
    v.left.setCurrentText("A")
    v.right.setCurrentText("B")
    with qtbot.waitSignal(v.diff_ready, timeout=60000):
        v.compare()
    assert sorted(_col(v.model)) == ["EPS-0001", "SYS-0001"]
    v.document.setCurrentText("EPS")
    assert _col(v.model) == ["EPS-0001"]


def test_compare_from_the_baselines_tab_and_item_shortcut(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    _baseline(win, qtbot)
    win.session.update_item("SYS-0002", attrs={"owner": "q"}, why="x")
    win.baselines_view.select("PDR")
    with qtbot.waitSignal(win.diff_view.diff_ready, timeout=60000):
        win.baselines_view.compare_with_working_copy()
    assert win.tabs.currentWidget() is win.diff_view and _col(win.diff_view.model) == ["SYS-0002"]
    win.select_item("SYS-0002")
    win.diff_view.show_item("SYS-0002")
    assert win.diff_view.table.currentIndex().row() == 0


def test_diff_export(win: MainWindow, qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    _baseline(win, qtbot)
    win.session.update_item("SYS-0001", attrs={"owner": "z"}, why="x")
    v = win.diff_view
    v.left.setCurrentText("PDR")
    v.right.setCurrentText("Working copy")
    with qtbot.waitSignal(v.diff_ready, timeout=60000):
        v.compare()
    for suffix in ("html", "docx", "pdf", "csv"):
        target = tmp_path / f"diff.{suffix}"
        with qtbot.waitSignal(v.export_done, timeout=60000):
            v.export_file(target)
        assert target.stat().st_size > 50

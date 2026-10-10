"""GUI audit B3b/M5/M6/M7/M18: the window can be small, panels have a usable default size, empty states say what to do."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit

from rvs_gui.app import MainWindow, create_main_window
from rvs_gui.wizard import NewRequirementWizard


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.resize(1400, 900)
    w.show()
    assert w.open_project(minimal_project)
    return w


def test_the_window_can_be_made_small_with_a_project_open_and_a_notification_showing(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.select_item("EPS-0001")
    win.notification.show_message("error", "Something went wrong with this long message. " * 4)
    qtbot.wait(50)
    hint = win.minimumSizeHint()
    assert hint.height() <= 640 and hint.width() <= 1100, (hint.width(), hint.height())


def test_the_tab_widget_and_editor_form_may_shrink(win: MainWindow):
    assert win.editor.form_scroll.minimumHeight() <= 120
    for page in (win.trace_view, win.vcm_view, win.coverage_view, win.graph_view, win.changes_view, win.diff_view):
        assert page.minimumWidth() > 0 and page.minimumHeight() <= 220  # explicit, small: not the sum of its controls


@pytest.mark.parametrize("page", range(5))
def test_the_wizard_never_exceeds_760_by_560(win: MainWindow, qtbot, page: int):  # type: ignore[no-untyped-def]
    wizard = NewRequirementWizard(win.session, win, document="EPS")
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.check_parent("SYS-0001")
    wizard.statement.setPlainText("The EPS shall provide power.")
    for _ in range(page):
        wizard.next()
    qtbot.wait(30)
    assert wizard.width() <= 760 and wizard.height() <= 560, (page, wizard.width(), wizard.height())
    assert wizard.minimumSizeHint().width() <= 760 and wizard.minimumSizeHint().height() <= 560


def test_the_wizard_pages_say_which_step_they_are_and_finish_creates(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    wizard = NewRequirementWizard(win.session, win)
    qtbot.addWidget(wizard)
    titles = [wizard.page(i).title() for i in wizard.pageIds()]
    assert [t.split(":")[0] for t in titles] == [f"Step {n} of 5" for n in range(1, 6)]
    assert wizard.buttonText(wizard.WizardButton.FinishButton) == "Create requirement"


def test_the_problems_panel_starts_tall_enough_to_read(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    qtbot.wait(100)
    assert win.problems_panel.height() >= 180


def test_reason_has_its_own_full_width_row(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.select_item("EPS-0001")
    qtbot.wait(50)
    why = win.editor.why
    assert why.width() >= 240
    assert why.geometry().bottom() <= win.editor.save_button.geometry().top()  # above the buttons, not beside them
    assert why.width() > win.editor.save_button.width() * 2


def test_default_column_widths_give_the_id_little_and_the_title_the_rest(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    qtbot.wait(50)
    header = win.table.horizontalHeader()
    assert 70 <= header.sectionSize(0) <= 110
    assert header.sectionSize(2) >= 100  # the title takes what is left


def test_the_documents_dock_is_wide_enough_for_titles(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    qtbot.wait(100)
    assert win.doc_tree.width() >= 200


def test_first_launch_shows_a_welcome_pane(qtbot):  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.items_stack.currentWidget() is w.welcome
    texts = " ".join(label.text() for label in w.welcome.findChildren(QLabel))
    assert "Open a project, create one, or open an example" in texts
    assert not w.actions_by_id["export"].isEnabled() and not w.action_save.isEnabled()


def test_a_search_without_results_says_so(win: MainWindow):
    assert not win.no_match.isVisibleTo(win)
    win.filter_bar.search.setText("zzzz-nothing-matches")
    assert win.no_match.isVisibleTo(win) and "No items match" in win.no_match.text()
    win.filter_bar.search.setText("")
    assert not win.no_match.isVisibleTo(win)


def test_empty_changes_and_baselines_tables_show_a_hint(win: MainWindow):
    assert win.changes_view.empty_hint.isVisibleTo(win.changes_view)
    assert win.baselines_view.empty_hint.isVisibleTo(win.baselines_view)
    win.changes_view.create_request("A change", "Because", ["SYS-0001"])
    assert not win.changes_view.empty_hint.isVisibleTo(win.changes_view)


def test_an_item_without_problems_says_so(win: MainWindow):
    win.session.update_item("SYS-0001", text="Power is provided.")  # no 'shall': a finding
    clean = "EPS-0001"
    win.select_item(clean)
    assert win.editor.no_findings.isVisibleTo(win.editor) and not win.editor.item_findings.isVisibleTo(win.editor)
    dirty = next(i.uid for i in win.session.items if win.session.findings_for(i.uid))
    win.select_item(dirty)
    assert win.editor.item_findings.isVisibleTo(win.editor) and not win.editor.no_findings.isVisibleTo(win.editor)


def test_search_field_is_a_line_edit_with_a_name(win: MainWindow):
    assert isinstance(win.filter_bar.search, QLineEdit) and win.filter_bar.search.accessibleName() == "Search items"


def test_window_layout_is_remembered_between_runs(qtbot, minimal_project):  # type: ignore[no-untyped-def]
    from rvs_core import userconfig
    from rvs_gui.app import MainWindow

    first = MainWindow()
    qtbot.addWidget(first)
    first.table.horizontalHeader().resizeSection(0, 333)
    first.close()
    saved = userconfig.load()["layout"]
    assert saved.get("state") and saved.get("items_header")
    second = MainWindow()
    qtbot.addWidget(second)
    assert second.table.horizontalHeader().sectionSize(0) == 333


def test_a_damaged_layout_setting_is_ignored(monkeypatch, tmp_path):  # type: ignore[no-untyped-def]
    import json

    from rvs_core import userconfig

    (tmp_path / "settings.json").write_text(json.dumps({"layout": {"state": 5, "ok": "AAAA", "bad": "é"}}))
    monkeypatch.setenv("RVS_CONFIG_DIR", str(tmp_path))
    assert userconfig.load()["layout"] == {"ok": "AAAA"}

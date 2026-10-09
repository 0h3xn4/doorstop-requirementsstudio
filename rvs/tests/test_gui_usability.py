"""Shortcuts, autocomplete, glossary, new project / examples / recent, help, async open, crash handling."""

import shutil
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from conftest import EXAMPLES
from rvs_core import userconfig
from rvs_gui.app import MainWindow, create_main_window
from rvs_gui.shortcuts import SHORTCUTS


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    return w


# shortcuts --------------------------------------------------------------------------------------------------------
def test_every_shortcut_is_bound_documented_and_unique(win: MainWindow):
    keys = [default for default, _desc in SHORTCUTS.values()]
    assert len(keys) == len(set(keys))
    for action_id, (default, description) in SHORTCUTS.items():
        action = win.actions_by_id[action_id]
        assert action.shortcut() == QKeySequence(default), action_id
        assert description
    for required in (
        "open_project",
        "save",
        "find",
        "go_to",
        "export",
        "import_items",
        "new_requirement",
        "next_problem",
        "help",
        "toggle_mode",
    ):
        assert required in SHORTCUTS


def test_shortcut_overrides_from_the_user_config_are_applied(qtbot, minimal_project: Path):  # type: ignore[no-untyped-def]
    userconfig.set_shortcut("export", "Ctrl+Alt+E")
    w = create_main_window()
    qtbot.addWidget(w)
    assert w.actions_by_id["export"].shortcut() == QKeySequence("Ctrl+Alt+E")


def test_shortcut_help_dialog_lists_all_actions(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.shortcuts import ShortcutsDialog

    dlg = ShortcutsDialog(win)
    qtbot.addWidget(dlg)
    text = dlg.table.model().index(0, 0).data()
    assert text and dlg.table.model().rowCount() == len(SHORTCUTS)


def test_ctrl_f_focuses_the_search_field_and_tab_keys_switch_tabs(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.activateWindow()
    qtbot.waitUntil(lambda: win.isActiveWindow(), timeout=2000)
    QTest.keyClick(win, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert win.filter_bar.search.hasFocus()
    QTest.keyClick(win, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
    assert win.tabs.currentWidget() is win.vcm_view
    win.actions_by_id["tab_1"].trigger()
    assert win.tabs.currentIndex() == 0


def test_go_to_item_and_problem_navigation(win: MainWindow):
    win.session.update_item("SYS-0001", text="Power is provided.")
    win.session.update_item("EPS-0002", text="Also not stated.")
    assert win.go_to("eps-0002") is True and win.editor.current_uid == "EPS-0002"
    assert win.go_to("NOPE-1") is False and "NOPE-1" in win.notification.text()
    win.editor.revert()
    first = win.next_problem()
    second = win.next_problem()
    assert first is not None and second is not None and first != second
    assert win.previous_problem() == first


# autocomplete (local data only) ------------------------------------------------------------------------------------
def test_uid_fields_complete_the_last_token_from_project_ids(win: MainWindow):
    win.select_item("EPS-0001")
    parents = win.editor.field("parents")
    assert parents.suggestions("SYS-0") == ["SYS-0001", "SYS-0002", "SYS-0003"]
    assert parents.suggestions("SYS-0001, SYS-0003, SYS-0002") == []  # nothing left after a full match
    assert parents.suggestions("SYS-0001, SYS-0") == ["SYS-0001, SYS-0002", "SYS-0001, SYS-0003"]  # no duplicates
    assert "EPS-0002" not in parents.suggestions("")  # parent field only offers the parent document's items
    links = win.editor.field("link_satisfies")
    assert "EPS-0002" in links.suggestions("EPS-000")  # typed links may point anywhere


def test_text_fields_complete_from_existing_values(win: MainWindow):
    win.select_item("SYS-0001")
    assert "systems" in win.editor.field("owner").completer().model().stringList()


# glossary -------------------------------------------------------------------------------------------------------------
def test_glossary_dialog_adds_an_acronym_and_clears_the_finding(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.glossary_dialog import GlossaryDialog

    win.session.update_item("SYS-0001", text="The spacecraft shall power the OBC.")
    assert any(f.code == "RVS-RULE-UNDEFINED-ACRONYM" and f.uid == "SYS-0001" for f in win.session.findings)
    dlg = GlossaryDialog(win.session)
    qtbot.addWidget(dlg)
    assert any(dlg.acronyms.item(r, 0).text() == "EPS" for r in range(dlg.acronyms.rowCount()))
    dlg.add_acronym("OBC", "On-Board Computer")
    dlg.add_term("Eclipse", "Period in the Earth's shadow")
    dlg.save()
    assert not any(f.code == "RVS-RULE-UNDEFINED-ACRONYM" and f.uid == "SYS-0001" for f in win.session.findings)
    import yaml

    data = yaml.safe_load((win.session.root / "config" / "glossary.yaml").read_text())  # type: ignore[operator]
    assert {"acronym": "OBC", "expansion": "On-Board Computer"} in data["acronyms"] and data["terms"][0][
        "term"
    ] == "Eclipse"


def test_glossary_dialog_rejects_blank_and_duplicate_entries(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.glossary_dialog import GlossaryDialog

    dlg = GlossaryDialog(win.session)
    qtbot.addWidget(dlg)
    assert dlg.add_acronym("", "x") is False and dlg.add_acronym("EPS", "again") is False
    assert dlg.add_acronym("A", "too short") is False  # an acronym has at least two characters


# new project, examples, recent ------------------------------------------------------------------------------------------
def test_new_project_dialog_and_creation(win: MainWindow, qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    from rvs_gui.project_dialogs import NewProjectDialog

    dlg = NewProjectDialog()
    qtbot.addWidget(dlg)
    assert [dlg.template.itemData(i) for i in range(dlg.template.count())][:2] == ["minimal", "satellite"]
    dlg.template.setCurrentIndex(dlg.template.findData("satellite"))
    assert "seven subsystem" in dlg.description.text()
    dlg.folder.setText(str(tmp_path / "newsat"))
    dlg.name.setText("New sat")
    dlg.git.setChecked(True)
    assert dlg.values() == (tmp_path / "newsat", "New sat", "satellite", True)
    assert win.create_project(tmp_path / "newsat", "New sat", "satellite", True) is True
    assert "New sat" in win.windowTitle() and win.session.root == tmp_path / "newsat"
    assert (tmp_path / "newsat" / ".git").is_dir() and win.table_model.rowCount() == 0
    assert userconfig.recent_projects()[0] == tmp_path / "newsat"


def test_creating_a_project_in_a_used_folder_is_a_message(win: MainWindow, tmp_path: Path):
    assert win.create_project(win.session.root, "x", "minimal", False) is False  # type: ignore[arg-type]
    assert win.notification.kind == "error" and "already" in win.notification.text()


def test_open_example_generates_a_copy_and_opens_it(win: MainWindow, tmp_path: Path):
    assert win.open_example("satellite", tmp_path / "example") is True
    assert win.table_model.rowCount() > 250 and "satellite" in win.windowTitle().lower()
    assert win.open_example("nope", tmp_path / "x") is False


def test_recent_projects_menu_lists_opened_projects(win: MainWindow, minimal_project: Path):
    texts = [a.text() for a in win.recent_menu.actions()]
    assert any(str(minimal_project) in t for t in texts)
    win.recent_menu.actions()[0].trigger()
    assert win.session.root == minimal_project


# help -----------------------------------------------------------------------------------------------------------------------
def test_help_viewer_shows_the_bundled_guide_offline(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    viewer = win.show_help("expert-walkthrough")
    qtbot.addWidget(viewer)
    assert "Expert" in viewer.browser.toPlainText() and viewer.browser.source().isLocalFile()
    assert win.actions_by_id["help"].shortcut() == QKeySequence("F1")


# async open ---------------------------------------------------------------------------------------------------------------------
def test_open_project_async_keeps_the_event_loop_running(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    root = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "satellite300", root, ignore=shutil.ignore_patterns(".rvs-cache"))
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    with qtbot.waitSignal(w.project_opened, timeout=60000) as sig:
        w.open_project_async(root)
        assert "Opening" in w.notification.text()
    assert sig.args == [True] and w.table_model.rowCount() > 300
    with qtbot.waitSignal(w.project_opened, timeout=60000) as bad:
        w.open_project_async(tmp_path / "nothing")
    assert bad.args == [False] and w.notification.kind == "error"


# crash handling -------------------------------------------------------------------------------------------------------------------
def test_unexpected_errors_show_a_friendly_message_and_save_a_report_without_content():
    from rvs_gui.crash import handle_exception

    shown: list[str] = []
    try:
        raise ValueError("secret requirement text SYS-0042")
    except ValueError:
        path = handle_exception(*sys.exc_info(), show=shown.append)
    assert path is not None and "secret" not in path.read_text() and "ValueError" in path.read_text()
    assert shown and "secret" not in shown[0] and "SYS-0042" not in shown[0] and str(path) in shown[0]
    assert "Traceback" not in shown[0]

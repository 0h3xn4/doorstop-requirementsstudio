"""GUI audit B4/B5/M2/M13/M14/M15: confirmations, glossary validation, baselines without Git, dialogs that validate."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QPushButton

from rvs_core.changecontrol.baselines import list_baselines
from rvs_gui.app import NOT_A_PROJECT, MainWindow, create_main_window
from rvs_gui.session import ProjectBusyError

ORIGINAL_CONFIRM_OVERWRITE = MainWindow.confirm_overwrite  # tests/conftest.py replaces the methods during a test
ORIGINAL_CONFIRM_REVERT = MainWindow.confirm_revert


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    return w


# B4: confirmations -------------------------------------------------------------------------------------------
def test_revert_asks_before_throwing_away_edits(win: MainWindow, monkeypatch):  # type: ignore[no-untyped-def]
    asked: list[str] = []
    monkeypatch.setattr(MainWindow, "confirm_revert", lambda self, uid: asked.append(uid) or False)
    win.editor.confirm_discard = win.confirm_revert  # re-bind to the patched method
    win.select_item("EPS-0001")
    win.editor.statement.setPlainText("The EPS shall be changed.")
    assert win.editor.revert() is False
    assert asked == ["EPS-0001"] and "changed" in win.editor.statement.toPlainText()
    monkeypatch.setattr(MainWindow, "confirm_revert", lambda self, uid: True)
    win.editor.confirm_discard = win.confirm_revert
    assert win.editor.revert() is True
    assert "changed" not in win.editor.statement.toPlainText() and not win.editor.is_dirty()


def test_revert_does_not_ask_when_nothing_changed(win: MainWindow):
    calls: list[str] = []
    win.editor.confirm_discard = lambda uid: calls.append(uid) or False
    win.select_item("EPS-0001")
    assert win.editor.revert() is True and calls == []


def test_revert_button_and_menu_action_follow_the_dirty_state(win: MainWindow):
    win.select_item("EPS-0001")
    assert not win.action_save.isEnabled() and not win.action_revert.isEnabled()
    win.editor.statement.setPlainText("The EPS shall be changed.")
    assert win.action_save.isEnabled() and win.action_revert.isEnabled()
    assert win.editor.save_button.isEnabled() and win.editor.revert_button.isEnabled()
    win.editor.revert()
    assert not win.action_save.isEnabled()


def test_wizard_cancel_asks_only_when_something_was_entered(win: MainWindow, qtbot, monkeypatch):  # type: ignore[no-untyped-def]
    from rvs_gui.wizard import NewRequirementWizard

    asked: list[bool] = []
    answers = iter([False, True])
    monkeypatch.setattr(NewRequirementWizard, "confirm_cancel", lambda self: asked.append(True) or next(answers))
    wizard = NewRequirementWizard(win.session, win, document="EPS")
    qtbot.addWidget(wizard)
    wizard.show()
    assert not wizard.has_input()
    wizard.reject()
    assert asked == [] and not wizard.isVisible()  # nothing entered: closes at once
    wizard.show()
    wizard.statement.setPlainText("The EPS shall do things.")
    assert wizard.has_input()
    wizard.reject()  # Esc / Cancel: the user says "keep editing"
    assert asked == [True] and wizard.isVisible()
    wizard.reject()  # and then "discard"
    assert asked == [True, True] and not wizard.isVisible()


# B4: glossary -------------------------------------------------------------------------------------------------
def test_glossary_save_names_the_wrong_rows_and_keeps_the_dialog_open(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QTableWidgetItem

    from rvs_gui.glossary_dialog import GlossaryDialog

    dlg = GlossaryDialog(win.session)
    qtbot.addWidget(dlg)
    before = (win.session.root / "config" / "glossary.yaml").read_bytes()  # type: ignore[operator]
    row = dlg.acronyms.rowCount()
    dlg.acronyms.insertRow(row)
    dlg.acronyms.setItem(row, 0, QTableWidgetItem("X"))
    dlg.acronyms.setItem(row, 1, QTableWidgetItem("Too short"))
    dlg.acronyms.insertRow(row + 1)
    dlg.acronyms.setItem(row + 1, 0, QTableWidgetItem("OBC"))
    dlg.acronyms.setItem(row + 1, 1, QTableWidgetItem(""))
    dlg.terms.insertRow(0)
    dlg.terms.setItem(0, 0, QTableWidgetItem("Eclipse"))
    assert dlg.save() is False
    text = dlg.message.text()
    assert f"row {row + 1}" in text and f"row {row + 2}" in text and "too short" in text and "needs" in text
    assert "Terms, row 1" in text
    assert (win.session.root / "config" / "glossary.yaml").read_bytes() == before  # type: ignore[operator]
    dlg._accept()  # noqa: SLF001 - the Save button
    assert dlg.result() == 0  # still open


def test_glossary_add_button_goes_through_validation(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.glossary_dialog import GlossaryDialog

    dlg = GlossaryDialog(win.session)
    qtbot.addWidget(dlg)
    rows = dlg.acronyms.rowCount()
    dlg.new_acronym.setText("A")
    dlg.new_expansion.setText("Too short")
    add = next(b for b in dlg.findChildren(QPushButton) if b.text() == "Add acronym")
    add.click()
    assert dlg.acronyms.rowCount() == rows and "too short" in dlg.message.text()
    dlg.new_acronym.setText("OBC")
    dlg.new_expansion.setText("On-Board Computer")
    add.click()
    assert dlg.acronyms.rowCount() == rows + 1 and dlg.new_acronym.text() == "" and dlg.message.text() == ""


# B5: baselines ------------------------------------------------------------------------------------------------
def test_baseline_dialog_offers_version_control_when_there_is_none(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.baseline_dialog import NewBaselineDialog

    dlg = NewBaselineDialog(win.session)
    qtbot.addWidget(dlg)
    dlg.show()
    assert not dlg.has_repo and dlg.use_git.isVisibleTo(dlg) and not dlg.init_git()
    dlg.name.setText("PDR")
    dlg.description.setText("Preliminary design review")
    assert not dlg.create_button.isEnabled() and "version control" in dlg.problem.text()
    dlg.use_git.setChecked(True)
    assert dlg.create_button.isEnabled() and dlg.init_git()
    assert dlg.create_button.text() == "Create permanent baseline"
    assert "cannot be edited or deleted and its name cannot be reused" in dlg.permanent_note.text()


def test_baseline_dialog_has_no_git_option_inside_a_repository(qtbot, git_project: Path):  # type: ignore[no-untyped-def]
    from rvs_gui.baseline_dialog import NewBaselineDialog

    w = create_main_window()
    qtbot.addWidget(w)
    assert w.open_project(git_project)
    dlg = NewBaselineDialog(w.session)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.has_repo and not dlg.use_git.isVisibleTo(dlg) and not dlg.init_git()


def test_baseline_with_version_control_turned_on_from_the_gui(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    view = win.baselines_view
    with qtbot.waitSignal(view.baseline_done, timeout=60000) as done:
        view.create_baseline("PDR", "Review", {}, init_git=True)
        assert win.session.busy  # edits are refused while the worker writes files
        with pytest.raises(ProjectBusyError):
            win.session.update_item("SYS-0001", text="Power is provided.")
    assert done.args == ["PDR", ""]
    assert not win.session.busy and [b.name for b in list_baselines(win.session.root)] == ["PDR"]  # type: ignore[arg-type]
    assert (win.session.root / ".git").is_dir()  # type: ignore[operator]


def test_a_missing_repository_is_explained_without_command_line_advice(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    view = win.baselines_view
    with qtbot.waitSignal(view.baseline_done, timeout=60000) as done:
        view.create_baseline("PDR", "Review", {})
    assert done.args[1]
    text = win.notification.text()
    assert win.notification.kind == "error" and "version control" in text
    assert "rvs " not in text and "git init" not in text and "--init-git" not in text
    assert not win.session.busy


def test_editing_is_refused_with_a_message_while_a_baseline_is_created(win: MainWindow):
    win.select_item("EPS-0001")
    win.session.begin_busy("baseline X is being created")
    try:
        win.editor.statement.setPlainText("The EPS shall be changed.")
        assert win.editor.save() is False
        assert "Please wait" in win.notification.text()
        assert not win.action_new.isEnabled() and not win.action_save.isEnabled()
    finally:
        win.session.end_busy()
    assert win.action_new.isEnabled()


# M2: notifications --------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind,word", [("error", "Error"), ("warning", "Warning"), ("success", "Success"), ("info", "Information")]
)
def test_notifications_name_their_severity_in_words(win: MainWindow, kind: str, word: str):
    n = win.notification
    n.show_message(kind, "Something <b>happened</b>")
    assert n.display_text().startswith(f"{word}:") and n.text() == "Something <b>happened</b>"
    assert n.accessibleName().startswith(f"{word}:")
    assert word in n._label.text() and "&lt;b&gt;" in n._label.text()  # noqa: SLF001 - the message itself is escaped
    assert n._icon.pixmap() is not None and not n._icon.pixmap().isNull()  # noqa: SLF001


def test_the_notification_close_button_is_labelled(win: MainWindow):
    close = win.notification.close_button
    assert "Dismiss" in close.toolTip() and close.accessibleName() == "Dismiss notification"
    win.notification.show_message("info", "x")
    close.click()
    assert not win.notification.isVisible()


# M13/M14: dialogs that validate ----------------------------------------------------------------------------
def test_new_project_dialog_validates_and_stays_open(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    from rvs_gui.project_dialogs import NewProjectDialog

    dlg = NewProjectDialog()
    qtbot.addWidget(dlg)
    assert dlg.ok_button.text() == "Create project" and not dlg.ok_button.isEnabled()
    assert "folder" in dlg.problem.text()
    dlg.folder.setText(str(tmp_path / "p"))
    assert "name" in dlg.problem.text()
    dlg.accept()
    assert dlg.result() == 0
    dlg.name.setText("P")
    assert dlg.ok_button.isEnabled() and dlg.problem.text() == ""
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "file.txt").write_text("x")
    dlg.folder.setText(str(tmp_path / "used"))
    assert not dlg.ok_button.isEnabled() and "not empty" in dlg.problem.text()
    dlg.folder.setText(str(tmp_path / "p"))
    dlg.accept()
    assert dlg.result() == 1


def test_creating_a_project_points_at_the_first_step(win: MainWindow, tmp_path: Path):
    assert win.create_project(tmp_path / "fresh", "Fresh", "minimal", False)
    assert win.notification.text() == "Project created. Press Ctrl+N to add your first requirement."
    assert win.notification.kind == "success"


def test_export_dialog_validates_the_path_and_labels_its_button(win: MainWindow, qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    from rvs_gui.export_dialog import ExportDialog

    dlg = ExportDialog(win.session)
    qtbot.addWidget(dlg)
    assert dlg.ok_button.text() == "Export" and not dlg.ok_button.isEnabled()
    dlg.accept()
    assert dlg.result() == 0 and "Choose where" in dlg.problem.text()
    dlg.path.setText(str(tmp_path / "missing" / "out"))
    assert not dlg.ok_button.isEnabled() and "does not exist" in dlg.problem.text()
    dlg.path.setText(str(tmp_path / "out"))
    assert dlg.ok_button.isEnabled()
    assert dlg.help.wordWrap() and dlg.minimumWidth() >= 500 and dlg.help.text()


def test_new_requirement_dialog_validates_and_has_a_size(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.dialogs import NewItemDialog

    dlg = NewItemDialog(win.session, document="EPS")
    qtbot.addWidget(dlg)
    assert dlg.minimumWidth() >= 440 and dlg.help.wordWrap()
    assert dlg.ok_button.text() == "Create requirement" and not dlg.ok_button.isEnabled()
    dlg.title.setText("Thing")
    dlg.parents.setText("SYS-9999")
    assert not dlg.ok_button.isEnabled() and "SYS-9999" in dlg.problem.text()
    dlg.accept()
    assert dlg.result() == 0
    dlg.parents.setText("SYS-0001")
    assert dlg.ok_button.isEnabled()
    ver = NewItemDialog(win.session, kind="verification")
    qtbot.addWidget(ver)
    ver.title.setText("Check")
    assert not ver.ok_button.isEnabled() and "at least one" in ver.problem.text()


# M15: failed open -----------------------------------------------------------------------------------------------
def test_opening_a_folder_that_is_not_a_project_is_explained_and_the_old_project_stays(win: MainWindow, tmp_path: Path):
    other = tmp_path / "plain"
    other.mkdir()
    old = win.session.root
    assert win.open_project(other) is False
    text = win.notification.text()
    assert text.startswith(NOT_A_PROJECT) and "previous project" in text and "still open" in text
    assert win.session.root == old and win.editor.current_uid is None or win.session.root == old


def test_opening_a_missing_folder_says_so(win: MainWindow, tmp_path: Path):
    assert win.open_project(tmp_path / "nope") is False
    assert "does not exist" in win.notification.text() and "still open" in win.notification.text()


def test_async_open_failure_mentions_the_previous_project(win: MainWindow, qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    other = tmp_path / "plain"
    other.mkdir()
    with qtbot.waitSignal(win.project_opened, timeout=30000) as done:
        win.open_project_async(other)
    assert done.args == [False] and "still open" in win.notification.text()


def _click_box_button(label: str) -> None:
    """Press the named button of the message box that is open (the question is modal: call this from a timer)."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMessageBox) and widget.isVisible():
            for button in widget.buttons():
                if button.text() == label:
                    button.click()
                    return
    raise AssertionError(f"no open message box with a '{label}' button")


@pytest.mark.parametrize("label,expected", [("Replace", True), ("Keep the existing file", False)])
def test_overwrite_question_uses_plain_labels(win: MainWindow, label: str, expected: bool):
    from PySide6.QtCore import QTimer

    QTimer.singleShot(100, lambda: _click_box_button(label))
    assert ORIGINAL_CONFIRM_OVERWRITE(win, Path("x.csv")) is expected


@pytest.mark.parametrize("label,expected", [("Discard changes", True), ("Keep editing", False)])
def test_revert_question_is_a_real_dialog_with_plain_labels(win: MainWindow, label: str, expected: bool):
    from PySide6.QtCore import QTimer

    QTimer.singleShot(100, lambda: _click_box_button(label))
    assert ORIGINAL_CONFIRM_REVERT(win, "EPS-0001") is expected

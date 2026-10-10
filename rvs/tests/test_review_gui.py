"""Regressions for defects found in the GUI by the review pass."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QDialog

from conftest import EXAMPLES
from rvs_core import userconfig
from rvs_gui.app import MainWindow, create_main_window


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    return w


# editor ----------------------------------------------------------------------------------------------------------------------------
def test_a_multi_line_text_field_is_clean_after_saving(win: MainWindow):
    win.select_item("SYS-0001")
    win.editor.field("rationale").setPlainText("line one\nline two")
    assert win.editor.is_dirty()
    assert win.editor.save()
    assert not win.editor.is_dirty()
    assert win.select_item("SYS-0002")  # navigation is not blocked by a phantom edit
    win.select_item("SYS-0001")
    assert not win.editor.is_dirty()


def test_opening_another_project_clears_the_editor_and_the_side_panels(win: MainWindow, tmp_path: Path):
    win.select_item("SYS-0001")
    assert win.create_project(tmp_path / "other", "Other", "minimal", False)
    assert win.editor.current_uid is None and not win.editor.isEnabled()
    assert "SYS-0001" not in win.editor.heading.text()
    assert win.graph_view.uid is None
    win.editor.statement.setPlainText("typing into nothing")
    assert not win.editor.is_dirty()  # nothing to save to, so nothing is pending


def test_the_form_follows_a_changed_vocabulary_without_marking_the_item_edited(win: MainWindow):
    vocab = win.session.root / "config" / "vocab.yaml"  # type: ignore[operator]
    data = yaml.safe_load(vocab.read_text(encoding="utf-8"))
    data["values"]["status"].append("frozen")
    vocab.write_text(yaml.safe_dump(data), encoding="utf-8")
    win.session.update_item("EPS-0001", attrs={})  # no-op edit; refresh below reloads the config
    win.session.refresh()
    item_file = win.session.root / "EPS" / "EPS-0001.yml"  # type: ignore[operator]
    text = item_file.read_text(encoding="utf-8").replace("status: draft", "status: frozen")
    item_file.write_text(text, encoding="utf-8")
    win.session.refresh()
    win.editor.load("EPS-0001")
    assert win.editor.field("status").currentText() == "frozen" and not win.editor.is_dirty()


def test_clear_suspect_links_never_discards_unsaved_edits(win: MainWindow):
    win.session.update_item("SYS-0002", text="The spacecraft shall change its power plan.")
    win.select_item("EPS-0001")
    win.editor.statement.setPlainText("The EPS shall be edited but not saved.")
    win.editor.clear_suspect()
    assert win.editor.is_dirty() and "edited but not saved" in win.editor.statement.toPlainText()
    assert win.notification.kind in ("warning", "error")


def test_glossary_additions_reach_the_editor_highlighting(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.glossary_dialog import GlossaryDialog

    win.select_item("SYS-0001")
    dlg = GlossaryDialog(win.session, win)
    qtbot.addWidget(dlg)
    dlg.add_acronym("OBC", "On-Board Computer")
    dlg.save()
    win.editor.load("SYS-0001")
    assert "OBC" in win.editor.highlighter.known


# window state ---------------------------------------------------------------------------------------------------------------------------
def test_the_status_filter_survives_a_refresh_and_go_to_reveals_hidden_items(win: MainWindow):
    win.filter_bar.status.setCurrentText("draft")
    shown = win.table_proxy.rowCount()
    assert 0 < shown < win.table_model.rowCount()
    win.session.refresh()
    assert win.filter_bar.status.currentText() == "draft" and win.table_proxy.rowCount() == shown
    approved = next(i.uid for i in win.session.items if i.attrs.get("status") != "draft" and i.normative)
    assert win.go_to(approved)
    assert win.table_proxy.rowCount() == win.table_model.rowCount() and win.table.currentIndex().isValid()


def test_next_problem_from_an_item_without_problems_goes_to_the_neighbour(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    root = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "satellite300", root, ignore=shutil.ignore_patterns(".rvs-cache"))
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(root)
    problems = w.problem_uids()
    order = [i.uid for i in w.session.items]
    clean = next(u for u in order if u not in problems and any(order.index(p) > order.index(u) for p in problems))
    assert w.go_to(clean)
    expected = next(p for p in problems if order.index(p) > order.index(clean))
    assert w.next_problem() == expected
    assert w.go_to(clean)
    before = [p for p in problems if order.index(p) < order.index(clean)]
    if before:
        assert w.previous_problem() == before[-1]


def test_tree_clicks_select_once_however_often_the_project_was_refreshed(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    for _ in range(5):
        win.session.refresh()
    seen: list[str] = []
    win.doc_tree.item_selected.connect(seen.append)
    node = win.doc_tree._item_nodes["SYS-0002"]  # noqa: SLF001
    win.doc_tree.setCurrentIndex(node.index())
    assert seen == ["SYS-0002"]


def test_creating_dialogs_are_refused_before_asking_when_edits_are_pending(win: MainWindow, monkeypatch):  # type: ignore[no-untyped-def]
    opened: list[str] = []
    monkeypatch.setattr("rvs_gui.wizard.NewRequirementWizard.exec", lambda self: opened.append("wizard") or 0)
    monkeypatch.setattr("rvs_gui.dialogs.NewItemDialog.exec", lambda self: opened.append("dialog") or 0)
    win.select_item("SYS-0001")
    win.editor.statement.setPlainText("The spacecraft shall change.")
    win.new_requirement_dialog()
    win.new_verification_dialog()
    assert opened == [] and win.notification.kind == "warning"


def test_change_request_form_keeps_typed_text_across_refreshes(win: MainWindow):
    win.session.store().create("First", "", "me")
    win.session.refresh()
    view = win.changes_view
    view.select("CR-0001")
    view.title.setText("Typed but not saved")
    win.session.refresh()
    assert view.title.text() == "Typed but not saved"


def test_the_active_change_request_does_not_follow_you_to_another_project(win: MainWindow, tmp_path: Path):
    win.session.store().create("First", "", "me")
    win.session.set_active_cr("CR-0001")
    assert win.create_project(tmp_path / "other", "Other", "minimal", False)
    assert win.session.active_cr is None
    assert win.create_item("SYS", "New requirement") is not None  # no "CR-0001 does not exist"


def test_a_broken_configuration_on_refresh_is_shown_not_swallowed(win: MainWindow):
    (win.session.root / "config" / "vocab.yaml").write_text("values: [broken\n", encoding="utf-8")  # type: ignore[operator]
    win.notification.dismiss()
    win.session.refresh()
    assert win.notification.kind == "error" and "vocab.yaml" in win.notification.text()


# opening ------------------------------------------------------------------------------------------------------------------------------
def test_an_async_open_does_not_overwrite_work_started_meanwhile(qtbot, minimal_project: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    other = tmp_path / "other"
    shutil.copytree(minimal_project, other)
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    w.select_item("SYS-0001")
    with qtbot.waitSignal(w.project_opened, timeout=30000) as sig:
        w.open_project_async(other)
        w.editor.statement.setPlainText("Typed while the other project was opening.")
    assert sig.args == [False] and w.session.root == minimal_project and w.editor.is_dirty()


def test_a_synchronous_open_waits_for_an_asynchronous_one(qtbot, minimal_project: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    other = tmp_path / "other"
    shutil.copytree(minimal_project, other)
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    with qtbot.waitSignal(w.project_opened, timeout=30000):
        w.open_project_async(minimal_project)
        assert w.open_project(other) is False and "being opened" in w.notification.text()
    assert w.session.root == minimal_project


# closing, exporting, errors --------------------------------------------------------------------------------------------------------------
def test_closing_the_window_also_closes_the_guide_and_asks_about_unsaved_edits(win: MainWindow, monkeypatch):  # type: ignore[no-untyped-def]
    viewer = win.show_help()
    win.select_item("SYS-0001")
    win.editor.statement.setPlainText("Unsaved text.")
    monkeypatch.setattr(MainWindow, "ask_unsaved", lambda self: "cancel")
    assert win.close() is False and win.isVisible() and viewer.isVisible()
    monkeypatch.setattr(MainWindow, "ask_unsaved", lambda self: "discard")
    assert win.close() is True and not viewer.isVisible()


def test_exporting_over_an_existing_file_asks_first(win: MainWindow, tmp_path: Path, monkeypatch, qtbot):  # type: ignore[no-untyped-def]
    from rvs_core.exporters.export_request import ExportRequest

    target = tmp_path / "report.csv"
    target.write_text("precious")
    monkeypatch.setattr(MainWindow, "confirm_overwrite", lambda self, path: False)
    win.export_to(ExportRequest("vcm", "csv"), target)
    assert target.read_text() == "precious"
    monkeypatch.setattr(MainWindow, "confirm_overwrite", lambda self, path: True)
    with qtbot.waitSignal(win.export_done, timeout=30000):
        win.export_to(ExportRequest("vcm", "csv"), target)
    assert target.read_text() != "precious"


def test_exporting_a_matrix_tab_without_a_matrix_is_a_message(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    messages: list[tuple[str, str]] = []
    w.vcm_view.message.connect(lambda k, t: messages.append((k, t)))
    w.vcm_view.export_file(tmp_path / "x.csv")
    assert messages and messages[0][0] in ("info", "error")


def test_disk_errors_in_slots_are_messages(win: MainWindow, monkeypatch, qtbot):  # type: ignore[no-untyped-def]
    def boom(*_a: object, **_k: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("rvs_gui.session.ProjectSession.update_item", boom)
    win.set_mode("expert")
    row = win.table_model.row_of("SYS-0001")
    idx = win.table_model.index(
        row, [c.key for c in __import__("rvs_gui.models", fromlist=["COLUMNS"]).COLUMNS].index("owner")
    )
    assert win.table_model.setData(idx, "someone") is False and win.notification.kind == "error"
    win.select_item("SYS-0001")
    win.editor.field("owner").setText("changed")
    assert win.editor.save() is False and "changed" in win.editor.field("owner").text()
    from rvs_gui.glossary_dialog import GlossaryDialog

    monkeypatch.setattr("rvs_gui.glossary_dialog.save_glossary", boom)
    dlg = GlossaryDialog(win.session, win)
    qtbot.addWidget(dlg)
    dlg.add_acronym("ZZZ", "Test")
    dlg.save()
    assert "space" in dlg.message.text().lower()


# user configuration ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "settings",
    [
        {"geometry": 5},
        {"geometry": "ü"},
        {"shortcuts": []},
        {"shortcuts": {"save": 5}},
        {"recent": 5},
        {"recent": [1, None]},
        {"mode": 5},
        {"theme": []},
        [1, 2],
        "text",
    ],
)
def test_corrupt_settings_never_stop_the_application_starting(qtbot, settings: object):  # type: ignore[no-untyped-def]
    userconfig.config_dir().mkdir(parents=True, exist_ok=True)
    (userconfig.config_dir() / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    w = create_main_window()
    qtbot.addWidget(w)
    assert w.mode in ("guided", "expert")


# dialogs ------------------------------------------------------------------------------------------------------------------------------------
def test_cancelled_dialogs_are_released(win: MainWindow, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("rvs_gui.wizard.NewRequirementWizard.exec", lambda self: 0)
    monkeypatch.setattr("rvs_gui.glossary_dialog.GlossaryDialog.exec", lambda self: 0)
    for _ in range(5):
        win.new_requirement_dialog()
        win.glossary_dialog()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(win.findChildren(QDialog)) == 0 and Qt  # noqa: PLR2004


def test_recent_list_hides_projects_that_no_longer_exist(win: MainWindow, tmp_path: Path):
    gone = tmp_path / "gone"
    gone.mkdir()
    userconfig.add_recent(gone)
    shutil.rmtree(gone)
    win._refresh_recent()  # noqa: SLF001
    assert not any(str(gone) in a.text() for a in win.recent_menu.actions())


def test_an_unreadable_shortcut_override_falls_back_to_the_default(qtbot):  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QKeySequence

    userconfig.set_shortcut("save", "not a key")
    w = create_main_window()
    qtbot.addWidget(w)
    assert w.actions_by_id["save"].shortcut() == QKeySequence("Ctrl+S")


def test_the_wizard_explains_a_parent_document_without_requirements(win: MainWindow, qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    from rvs_gui.wizard import NewRequirementWizard

    assert win.create_project(tmp_path / "fresh", "Fresh", "minimal", False)
    wiz = NewRequirementWizard(win.session, win)
    qtbot.addWidget(wiz)
    wiz.document.setCurrentText("SUB")
    assert "no requirements yet" in wiz.parent_help.text()

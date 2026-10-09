"""Guided mode (wizard, field help) and expert mode (dense table, inline editing)."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from rvs_core import userconfig
from rvs_core.authoring import read_history
from rvs_gui.app import MainWindow, create_main_window
from rvs_gui.models import COLUMNS


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    return w


def _col(key: str) -> int:
    return [c.key for c in COLUMNS].index(key)


# mode switching ------------------------------------------------------------------------------------------
def test_first_run_is_guided_and_the_choice_is_remembered(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    assert win.mode == "guided" and win.action_mode_guided.isChecked()
    win.set_mode("expert")
    assert win.mode == "expert" and win.action_mode_expert.isChecked() and userconfig.load()["mode"] == "expert"
    again = create_main_window()
    qtbot.addWidget(again)
    assert again.mode == "expert"


def test_unknown_mode_is_rejected(win: MainWindow):
    with pytest.raises(ValueError, match="expert"):
        win.set_mode("turbo")


def test_guided_mode_shows_field_help_and_expert_mode_hides_it(win: MainWindow):
    win.select_item("SYS-0001")
    assert "Why the requirement exists" in win.editor.field("rationale").toolTip()
    assert win.editor.help_visible() is True
    win.set_mode("expert")
    assert win.editor.help_visible() is False


def test_expert_mode_makes_the_table_dense_and_guided_comfortable(win: MainWindow):
    comfortable = win.table.verticalHeader().defaultSectionSize()
    win.set_mode("expert")
    assert win.table.verticalHeader().defaultSectionSize() < comfortable


# inline editing (expert) -------------------------------------------------------------------------------------
def test_guided_mode_table_is_read_only(win: MainWindow):
    idx = win.table_model.index(win.table_model.row_of("SYS-0001"), _col("status"))
    assert not (win.table_model.flags(idx) & Qt.ItemFlag.ItemIsEditable)


def test_expert_mode_edits_enum_and_text_cells_in_place(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.set_mode("expert")
    row = win.table_model.row_of("SYS-0001")
    status = win.table_model.index(row, _col("status"))
    assert win.table_model.flags(status) & Qt.ItemFlag.ItemIsEditable
    assert not (win.table_model.flags(win.table_model.index(row, _col("uid"))) & Qt.ItemFlag.ItemIsEditable)
    assert win.table_model.setData(status, "reviewed") is True
    assert win.session.item("SYS-0001").attrs["status"] == "reviewed"  # type: ignore[union-attr]
    assert read_history(win.session.root, "SYS-0001")[-1]["fields"] == ["status"]  # type: ignore[arg-type]
    title = win.table_model.index(win.table_model.row_of("SYS-0001"), _col("title"))
    assert win.table_model.setData(title, "Payload power (inline)") is True
    qtbot.wait(50)
    assert win.table_model.index(win.table_model.row_of("SYS-0001"), _col("title")).data() == "Payload power (inline)"


def test_inline_edit_with_an_invalid_value_is_refused_with_a_message(win: MainWindow):
    win.set_mode("expert")
    idx = win.table_model.index(win.table_model.row_of("SYS-0001"), _col("status"))
    assert win.table_model.setData(idx, "finished") is False
    assert win.notification.kind == "error" and "finished" in win.notification.text()
    assert win.session.item("SYS-0001").attrs["status"] == "draft"  # type: ignore[union-attr]


def test_inline_edit_of_a_baselined_item_asks_for_a_reason(win: MainWindow):
    win.session.update_item("SYS-0001", attrs={"status": "baselined"})
    win.set_mode("expert")
    asked: list[str] = []
    win.ask_reason = lambda uid: asked.append(uid) or "customer request"  # type: ignore[method-assign,func-returns-value]
    idx = win.table_model.index(win.table_model.row_of("SYS-0001"), _col("owner"))
    assert win.table_model.setData(idx, "someone") is True and asked == ["SYS-0001"]
    assert read_history(win.session.root, "SYS-0001")[-1]["why"] == "customer request"  # type: ignore[arg-type]
    win.ask_reason = lambda uid: ""  # type: ignore[method-assign]
    idx = win.table_model.index(win.table_model.row_of("SYS-0001"), _col("owner"))
    assert win.table_model.setData(idx, "other") is False and "reason" in win.notification.text().lower()


def test_enum_columns_use_a_combo_delegate_with_the_project_vocabulary(win: MainWindow):
    win.set_mode("expert")
    delegate = win.table.itemDelegateForColumn(_col("status"))
    editor = delegate.createEditor(win.table.viewport(), None, win.table_proxy.index(0, _col("status")))  # type: ignore[arg-type]
    assert isinstance(editor, QComboBox)
    assert [editor.itemText(i) for i in range(editor.count())] == [
        "draft",
        "reviewed",
        "approved",
        "baselined",
        "obsolete",
    ]


# wizard (guided) ----------------------------------------------------------------------------------------------
def _wizard(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.wizard import NewRequirementWizard

    wiz = NewRequirementWizard(win.session)
    qtbot.addWidget(wiz)
    return wiz


def test_wizard_pages_and_required_input(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    wiz = _wizard(win, qtbot)
    assert wiz.documents() == ["SYS", "EPS"]
    wiz.document.setCurrentText("EPS")
    assert wiz.parent_candidates() == ["SYS-0001", "SYS-0002", "SYS-0003"]  # the parent document's normative items
    assert not wiz.button(wiz.WizardButton.NextButton).isEnabled()  # a non-root requirement needs a parent
    wiz.check_parent("SYS-0002")
    assert wiz.button(wiz.WizardButton.NextButton).isEnabled()
    wiz.next()
    assert wiz.currentId() == 1 and not wiz.button(wiz.WizardButton.NextButton).isEnabled()  # needs a statement
    wiz.statement.setPlainText("The EPS shall charge the battery.")
    assert wiz.button(wiz.WizardButton.NextButton).isEnabled()


def test_wizard_shows_rule_findings_while_typing(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    wiz = _wizard(win, qtbot)
    wiz.document.setCurrentText("EPS")
    wiz.check_parent("SYS-0001")
    wiz.next()
    wiz.statement.setPlainText("The EPS provides adequate power.")
    text = wiz.live_findings.toPlainText()
    assert "does not contain 'shall'" in text and "adequate" in text
    wiz.statement.setPlainText("The EPS shall provide 28 V.")
    assert "does not contain 'shall'" not in wiz.live_findings.toPlainText()  # the shall finding is gone


def test_wizard_details_page_shows_every_template_field(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    wiz = _wizard(win, qtbot)
    cfg = win.session.cfg
    expected = {
        a.name
        for a in cfg.templates.kinds["requirements"].attributes
        if a.name not in ("rvs_schema_version",) and a.type != "ref-list"
    }  # type: ignore[union-attr]
    assert set(wiz.fields) == expected  # no field is hidden in guided mode
    assert "Why the requirement exists" in wiz.fields["rationale"].toolTip()


def test_wizard_creates_the_requirement_and_an_optional_verification_item(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    wiz = _wizard(win, qtbot)
    wiz.document.setCurrentText("EPS")
    wiz.check_parent("SYS-0002")
    wiz.statement.setPlainText("The EPS shall charge the battery within 90 minutes.")
    wiz.field_set("title", "Charge time")
    wiz.field_set("type", "performance")
    wiz.field_set("verify_method", "test")
    wiz.field_set("verify_level", "subsystem")
    wiz.verify_check.setChecked(True)
    spec = wiz.spec()
    assert spec.document == "EPS" and spec.parents == ["SYS-0002"] and spec.verification is not None
    uid = win.create_from_spec(spec)
    assert uid == "EPS-0004"
    item = win.session.item(uid)
    assert item is not None and item.attrs["title"] == "Charge time" and item.links == ("SYS-0002",)
    ver = win.session.item("VER-0004")
    assert ver is not None and ver.attrs["link_verifies"] == [uid] and ver.attrs["verify_method"] == "test"
    assert win.editor.current_uid == uid and win.notification.kind == "success"


def test_wizard_review_page_summarises_and_blocks_nothing_but_explains(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    wiz = _wizard(win, qtbot)
    wiz.document.setCurrentText("EPS")
    wiz.check_parent("SYS-0002")
    wiz.statement.setPlainText("The EPS charges.")
    wiz.field_set("title", "T")
    wiz.field_set("type", "functional")
    wiz.refresh_review()
    text = wiz.review.toPlainText()
    assert "EPS" in text and "SYS-0002" in text and "does not contain 'shall'" in text


def test_guided_new_requirement_action_opens_the_wizard_and_expert_the_quick_dialog(
    win: MainWindow, qtbot, monkeypatch
):  # type: ignore[no-untyped-def]
    opened: list[str] = []
    monkeypatch.setattr("rvs_gui.wizard.NewRequirementWizard.exec", lambda self: opened.append("wizard") or 0)
    monkeypatch.setattr("rvs_gui.dialogs.NewItemDialog.exec", lambda self: opened.append("dialog") or 0)
    win.new_requirement_dialog()
    win.set_mode("expert")
    win.new_requirement_dialog()
    assert opened == ["wizard", "dialog"]

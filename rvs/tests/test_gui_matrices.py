"""pytest-qt tests for the M3 views: typed links, traceability, VCM, coverage, impact, graph."""

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from conftest import EXAMPLES
from rvs_core.adapter import DoorstopProject
from rvs_gui.app import MainWindow, create_main_window


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    return w


def _cells(model, col: int = 0) -> list[str]:  # type: ignore[no-untyped-def]
    return [model.index(r, col).data() for r in range(model.rowCount())]


def test_tabs_exist_and_items_is_first(win: MainWindow):
    names = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert names[:5] == ["Items", "Traceability", "VCM", "Coverage", "Graph"]
    assert win.tabs.currentIndex() == 0


# typed links in the editor ---------------------------------------------------------------
def test_edit_typed_link_and_see_validation(win: MainWindow):
    assert win.select_item("EPS-0001")
    win.editor.field("link_satisfies").setText("SYS-0001")
    assert win.editor.save() is True
    assert win.session.item("EPS-0001").attrs["link_satisfies"] == ["SYS-0001"]  # type: ignore[union-attr]
    win.editor.field("link_refines").setText("SYS-0099")
    assert win.editor.save() is True  # saving is allowed; the problem is reported
    texts = [win.editor.item_findings.item(i).text() for i in range(win.editor.item_findings.count())]
    assert any("SYS-0099" in t for t in texts)
    assert any(f.code == "RVS-LINK-TARGET-MISSING" for f in win.session.findings)


def test_suspect_link_appears_and_can_be_cleared(win: MainWindow):
    win.select_item("SYS-0002")
    win.editor.field("title").setText("Eclipse operation changed")
    assert win.editor.save()
    assert any(f.code == "RVS-LINK-SUSPECT" and f.uid == "EPS-0001" for f in win.session.findings)
    win.select_item("EPS-0001")
    assert win.editor.clear_suspect_button.isEnabled()
    win.editor.why.setText("reviewed")
    win.editor.clear_suspect_button.click()
    assert not any(f.code == "RVS-LINK-SUSPECT" for f in win.session.findings)
    assert not win.editor.clear_suspect_button.isEnabled()


def test_create_verification_item_flow(win: MainWindow):
    uid = win.create_verification("VER", ["EPS-0002"])
    assert uid == "VER-0004"
    item = win.session.item(uid)
    assert item is not None and item.attrs["link_verifies"] == ["EPS-0002"] and item.attrs["verify_method"] == "test"
    assert win.editor.current_uid == uid
    win.tabs.setCurrentWidget(win.vcm_view)
    row = {r[0]: r for r in win.vcm_view.matrix.rows}["EPS-0002"]
    assert "VER-0004" in row[win.vcm_view.matrix.columns.index("Verification item")]


def test_new_verification_dialog_lists_verification_documents(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.dialogs import NewItemDialog

    dlg = NewItemDialog(win.session, kind="verification")
    qtbot.addWidget(dlg)
    assert dlg.documents() == ["VER"]
    dlg.title.setText("Check")
    dlg.parents.setText("EPS-0001, EPS-0002")
    assert dlg.values() == ("VER", "Check", ["EPS-0001", "EPS-0002"])


# traceability matrix -------------------------------------------------------------------------
def test_traceability_view(win: MainWindow):
    v = win.trace_view
    win.tabs.setCurrentWidget(v)  # hidden tabs refresh when first shown
    v.source.setCurrentText("SYS")
    v.target.setCurrentText("EPS")
    v.direction.setCurrentText("down")
    assert _cells(v.model) == ["SYS-0001", "SYS-0002", "SYS-0003"]
    win.session.create_item("SYS", "The spacecraft shall be lonely.", attrs={"title": "Lonely", "type": "functional"})
    assert "SYS-0005" in _cells(v.model)  # refreshed automatically after an edit
    row = _cells(v.model).index("SYS-0005")
    assert v.model.index(row, 0).data(Qt.ItemDataRole.BackgroundRole) is not None  # gap highlighted
    assert v.model.index(0, 0).data(Qt.ItemDataRole.BackgroundRole) is None


def test_traceability_view_up_direction(win: MainWindow):
    v = win.trace_view
    win.tabs.setCurrentWidget(v)
    v.source.setCurrentText("EPS")
    v.target.setCurrentText("SYS")
    v.direction.setCurrentText("up")
    assert _cells(v.model) == ["EPS-0001", "EPS-0002", "EPS-0003"]


# VCM -----------------------------------------------------------------------------------------------
def test_vcm_view_filters_and_export(win: MainWindow, tmp_path: Path):
    v = win.vcm_view
    assert v.model.rowCount() == 6
    v.document.setCurrentText("EPS")
    assert v.model.rowCount() == 3
    v.document.setCurrentIndex(0)
    v.only_gaps.setChecked(True)
    assert _cells(v.model) == ["SYS-0001", "SYS-0002", "SYS-0003"]
    v.only_gaps.setChecked(False)
    target = tmp_path / "vcm.csv"
    v.export_csv(target)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# Verification control matrix") and "Project: Minimal example" in text
    assert win.notification.kind == "success"


def test_vcm_shows_provenance_and_placeholder_note(win: MainWindow):
    assert "Minimal example" in win.vcm_view.provenance_label.text()
    assert "TODO-STANDARD" in win.vcm_view.notes_label.text()


# coverage ----------------------------------------------------------------------------------------------
def test_hidden_tabs_refresh_when_shown_not_before(win: MainWindow):
    win.session.create_item("SYS", "The spacecraft shall be lonely.", attrs={"title": "Lonely", "type": "functional"})
    assert win.vcm_view._stale is True  # noqa: SLF001 - nothing was rebuilt for a tab nobody is looking at
    win.tabs.setCurrentWidget(win.vcm_view)
    assert win.vcm_view._stale is False and "SYS-0005" in {r[0] for r in win.vcm_view.matrix.rows}  # noqa: SLF001


def test_coverage_view(win: MainWindow):
    win.tabs.setCurrentWidget(win.coverage_view)
    assert _cells(win.coverage_view.model) == ["SYS", "EPS", "VER"]
    assert win.coverage_view.model.index(0, 2).data() == "3"


# impact ---------------------------------------------------------------------------------------------------
def test_impact_panel_follows_selection(win: MainWindow):
    win.select_item("SYS-0002")
    p = win.impact_panel
    assert p.objectName() == "ImpactPanel"
    assert p.summary.text().startswith("2 items")
    top = p.tree.topLevelItem(0)
    assert top.text(0) == "EPS-0001" and top.child(0).text(0) == "VER-0001"
    assert [p.list_model.index(r, 0).data() for r in range(p.list_model.rowCount())] == ["EPS-0001", "VER-0001"]
    win.select_item("VER-0001")
    assert p.summary.text().startswith("0 items")


def test_impact_item_double_click_opens_it(win: MainWindow):
    win.select_item("SYS-0002")
    win.impact_panel.tree.itemDoubleClicked.emit(win.impact_panel.tree.topLevelItem(0), 0)
    assert win.editor.current_uid == "EPS-0001"


# graph ---------------------------------------------------------------------------------------------------------
def test_graph_view_shows_neighbourhood(win: MainWindow):
    win.select_item("EPS-0001")
    g = win.graph_view
    assert sorted(g.node_uids()) == ["EPS-0001", "SYS-0002", "VER-0001"]
    assert g.edge_count() == 2
    g.depth_box.setValue(2)
    assert "SYS-0002" in g.node_uids()


def test_graph_node_click_opens_the_item(win: MainWindow):
    win.select_item("EPS-0001")
    win.graph_view.click_node("SYS-0002")
    assert win.editor.current_uid == "SYS-0002"


# fast open / full validation ------------------------------------------------------------------------------
def test_open_is_fast_mode_and_full_validation_adds_doorstop_findings(win: MainWindow):
    assert not [f for f in win.session.findings if f.code.startswith("DOORSTOP-")]
    win.run_full_validation()
    assert any(f.code == "DOORSTOP-UNREVIEWED" for f in win.session.findings)
    win.session.refresh()  # any later edit goes back to the fast path
    assert not [f for f in win.session.findings if f.code.startswith("DOORSTOP-")]


def test_satellite_matrices_open_and_gaps_are_flagged(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    root = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "satellite300", root)
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(root)
    w.tabs.setCurrentWidget(w.vcm_view)
    assert w.vcm_view.model.rowCount() > 250
    w.tabs.setCurrentWidget(w.coverage_view)
    assert w.coverage_view.model.rowCount() == 10
    w.tabs.setCurrentWidget(w.trace_view)
    w.trace_view.source.setCurrentText("SYS")
    w.trace_view.target.setCurrentText("EPS")
    assert w.trace_view.model.rowCount() == 50
    assert DoorstopProject.open(root).items()

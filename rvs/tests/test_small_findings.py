"""Regressions for the smaller findings of the review pass (DEVIATIONS V24)."""

import os
import threading
import time
from pathlib import Path

import pytest
import yaml
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from rvs_core.adapter import DoorstopProject, ItemData
from rvs_core.validate import validate_project


def _aged(root: Path) -> None:
    old = time.time() - 600
    for p in root.rglob("*.yml"):
        os.utime(p, (old, old))


# core -------------------------------------------------------------------------------------------------------------------------------
def test_a_duplicate_key_in_an_item_file_is_reported_even_from_the_cache(minimal_project: Path):
    path = minimal_project / "EPS" / "EPS-0002.yml"
    path.write_text(path.read_text(encoding="utf-8") + "status: approved\n", encoding="utf-8")
    _aged(minimal_project)
    for _ in range(2):  # the second run is served from the item cache
        report = validate_project(minimal_project, doorstop=False)
        found = [f for f in report.findings if f.code == "RVS-ITEM-DUPLICATE-KEY"]
        assert len(found) == 1 and found[0].uid == "EPS-0002" and "status" in found[0].message
        assert report.exit_code == 1


def test_levels_sort_headings_first_and_numbers_numerically():
    def key(level: str) -> tuple[int, ...]:
        return ItemData("X-1", "X", level, "", "", True, False, True, False, "", ()).level_key

    order = sorted(["6.1", "6", "6.0", "1.10", "1.9", "1.2.0", "1.2", "1.2.1", "2"], key=key)
    assert order == ["1.2.0", "1.2", "1.2.1", "1.9", "1.10", "2", "6.0", "6", "6.1"]


def test_a_free_attribute_may_not_redefine_a_template_attribute(minimal_project: Path):
    path = minimal_project / "rvs-project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["free_attributes"] = [{"name": "status", "type": "string"}]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    report = validate_project(minimal_project, doorstop=False)
    assert report.exit_code == 3 and "status" in report.findings[0].message


def test_item_files_are_written_atomically(minimal_project: Path, monkeypatch):  # type: ignore[no-untyped-def]
    from rvs_core.authoring import EditService

    path = minimal_project / "SYS" / "SYS-0001.yml"
    before = path.read_bytes()

    def crash(*_a: object, **_k: object) -> None:
        raise OSError("power failure")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="power failure"):
        EditService(minimal_project).update_item("SYS-0001", text="The spacecraft shall change.")
    assert path.read_bytes() == before  # the old file is intact, not truncated
    assert not [p for p in path.parent.iterdir() if p.suffix == ".tmp"]  # and nothing is left behind


def test_concurrent_cache_saves_never_leave_a_damaged_cache(minimal_project: Path):
    _aged(minimal_project)
    DoorstopProject.open(minimal_project).items()

    def worker() -> None:
        for _ in range(15):
            project = DoorstopProject.open(minimal_project)
            project._cache.save("SYS", (0, 0), {})  # noqa: SLF001 - hammer the writer

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not list((minimal_project / ".rvs-cache").glob("*.tmp"))
    assert DoorstopProject.open(minimal_project).items()  # still readable (a bad cache is read as empty)


# exports ---------------------------------------------------------------------------------------------------------------------------------
def test_an_enum_value_outside_the_vocabulary_is_still_exported(minimal_project: Path):
    import xml.etree.ElementTree as ET
    from datetime import datetime

    from rvs_core.config import load_project_config
    from rvs_core.exporters.reqif import export_reqif
    from rvs_core.matrices import Provenance

    path = minimal_project / "EPS" / "EPS-0001.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: frozen"), encoding="utf-8")
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    xml = export_reqif(cfg, items, Provenance("0.1.0", "3.2", "P", "working copy", datetime(2026, 1, 2), "a"))
    labels = [
        e.get("LONG-NAME")
        for e in ET.fromstring(xml).iter("{http://www.omg.org/spec/ReqIF/20110401/reqif.xsd}ENUM-VALUE")
    ]  # noqa: S314
    assert "frozen" in labels and "draft" in labels


# GUI and threads -----------------------------------------------------------------------------------------------------------------------
def test_a_shortcut_override_that_duplicates_another_key_is_ignored(qtbot):  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QKeySequence

    from rvs_core import userconfig
    from rvs_gui.app import create_main_window

    userconfig.set_shortcut("export", "Ctrl+S")  # Ctrl+S is "save"
    w = create_main_window()
    qtbot.addWidget(w)
    assert w.actions_by_id["export"].shortcut() == QKeySequence("Ctrl+E")
    assert w.actions_by_id["save"].shortcut() == QKeySequence("Ctrl+S")


def test_follow_the_system_theme_changes_with_the_desktop(qtbot, monkeypatch):  # type: ignore[no-untyped-def]
    from rvs_gui import theme
    from rvs_gui.app import create_main_window

    monkeypatch.setattr("rvs_gui.theme.system_scheme", lambda: "light")
    w = create_main_window()
    qtbot.addWidget(w)
    w.set_theme("system")
    assert theme.TOKENS["background"] == theme.LIGHT["background"]
    monkeypatch.setattr("rvs_gui.theme.system_scheme", lambda: "dark")
    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert theme.TOKENS["background"] == theme.DARK["background"]
    w.set_theme("light")  # an explicit choice is not overridden by later desktop changes
    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert theme.TOKENS["background"] == theme.LIGHT["background"]


def test_a_worker_that_raises_a_non_exception_still_reports_and_restores_the_interval(qtbot):  # type: ignore[no-untyped-def]
    import sys

    from rvs_gui.jobs import run_in_background

    class Odd(BaseException):  # noqa: N818 - deliberately not an Exception
        pass

    before = sys.getswitchinterval()
    failures: list[Exception] = []

    def boom() -> None:
        raise Odd("not an Exception")

    run_in_background(boom, lambda _v: None, failures.append)
    qtbot.waitUntil(lambda: bool(failures), timeout=5000)
    assert "Odd" in str(failures[0]) or isinstance(failures[0], Exception)
    qtbot.waitUntil(lambda: sys.getswitchinterval() == before, timeout=2000)


def test_only_the_latest_comparison_is_shown(qtbot, minimal_project: Path, monkeypatch):  # type: ignore[no-untyped-def]
    from rvs_gui import diff_view
    from rvs_gui.app import create_main_window

    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    callbacks: list[tuple[object, object]] = []
    monkeypatch.setattr(diff_view, "run_in_background", lambda fn, done, failed: callbacks.append((done, failed)))
    view = w.diff_view
    view.compare()
    view.compare()
    first_done, second_done = callbacks[0][0], callbacks[1][0]
    newer, older = object(), object()
    monkeypatch.setattr(view, "_show_table", lambda: None)
    second_done(newer)  # type: ignore[operator]
    first_done(older)  # type: ignore[operator]  # arrives late: must not replace the newer result
    assert view.diff is newer


def test_the_shown_comparison_is_recoloured_when_the_theme_changes(qtbot, minimal_project: Path):  # type: ignore[no-untyped-def]
    from rvs_core.authoring import EditService
    from rvs_core.changecontrol.baselines import create_baseline
    from rvs_core.vcs.git import GitRepo
    from rvs_gui import theme
    from rvs_gui.app import create_main_window

    GitRepo.init(minimal_project)
    create_baseline(minimal_project, "B1", "x", user="a")
    EditService(minimal_project).update_item("SYS-0001", text="The spacecraft shall be different.", why="x")
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    w.diff_view.set_range("B1", None)
    with qtbot.waitSignal(w.diff_view.diff_ready, timeout=30000):
        w.diff_view.compare()
    assert theme.LIGHT["diff_ins"] in w.diff_view.detail.toHtml().lower() or "color:" in w.diff_view.detail.toHtml()
    w.set_theme("dark")
    assert theme.DARK["diff_ins"] in w.diff_view.detail.toHtml().lower()
    w.set_theme("light")

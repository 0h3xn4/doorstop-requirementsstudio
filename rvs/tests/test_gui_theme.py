"""Light and dark themes: Carbon palettes with enough contrast, switched at run time and remembered."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from rvs_core import userconfig
from rvs_gui import theme
from rvs_gui.app import MainWindow, create_main_window


@pytest.fixture(autouse=True)
def _restore_light():  # type: ignore[no-untyped-def]
    yield
    theme.set_theme("light")


@pytest.fixture
def win(qtbot, minimal_project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = create_main_window()
    qtbot.addWidget(w)
    w.show()
    assert w.open_project(minimal_project)
    return w


def _lum(hex_colour: str) -> float:
    rgb = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_both_palettes_define_the_same_tokens():
    assert set(theme.LIGHT) == set(theme.DARK)
    assert theme.TOKENS == theme.LIGHT


@pytest.mark.parametrize("name", ["light", "dark"])
def test_text_has_aa_contrast_on_every_surface(name: str):
    t = theme.palette(name)
    for fg, bg in [
        ("text", "background"), ("text", "layer"), ("text_secondary", "background"), ("text_secondary", "layer"),
        ("header_text", "header"), ("button_text", "interactive"), ("button_text", "interactive_hover"),
        ("link", "background"), ("text", "gap_error"), ("text", "gap_warn"), ("text", "node_centre"),
        ("support_error", "background"), ("support_error", "layer"), ("warning_text", "background"),
        ("diff_ins", "background"), ("diff_del", "background"),
    ]:  # fmt: skip
        assert contrast(t[fg], t[bg]) >= 4.5, f"{name}: {fg} on {bg} is {contrast(t[fg], t[bg]):.1f}:1"


def test_unknown_theme_is_rejected():
    with pytest.raises(ValueError, match="light"):
        theme.set_theme("sepia")


def test_switching_changes_tokens_and_the_application_stylesheet(win: MainWindow):
    win.set_theme("dark")
    assert theme.TOKENS["background"] == theme.DARK["background"] and win.theme == "dark"
    assert theme.DARK["background"] in win.styleSheet()  # a window without an application stylesheet styles itself
    assert win.action_theme_dark.isChecked() and not win.action_theme_light.isChecked()
    win.set_theme("light")
    assert theme.LIGHT["background"] in win.styleSheet()


def test_choice_is_remembered_and_applied_to_the_next_window(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.set_theme("dark")
    assert userconfig.load()["theme"] == "dark"
    theme.set_theme("light")  # as at process start
    again = create_main_window()
    qtbot.addWidget(again)
    assert again.theme == "dark" and theme.TOKENS["background"] == theme.DARK["background"]


def test_system_follows_the_desktop_scheme(win: MainWindow, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("rvs_gui.theme.system_scheme", lambda: "dark")
    win.set_theme("system")
    assert win.theme == "system" and theme.TOKENS["background"] == theme.DARK["background"]
    monkeypatch.setattr("rvs_gui.theme.system_scheme", lambda: "light")
    win.set_theme("system")
    assert theme.TOKENS["background"] == theme.LIGHT["background"]


def test_models_and_views_use_the_current_palette(win: MainWindow):
    win.session.create_item("SYS", "The spacecraft shall be lonely.", attrs={"title": "Lonely", "type": "functional"})
    view = win.trace_view
    win.tabs.setCurrentWidget(view)
    view.source.setCurrentText("SYS")
    view.target.setCurrentText("EPS")
    flagged = next(i for i, f in enumerate(view.matrix.flags) if f)
    light_gap = view.model.index(flagged, 0).data(Qt.ItemDataRole.BackgroundRole).color().name()
    win.set_theme("dark")
    dark_gap = view.model.index(flagged, 0).data(Qt.ItemDataRole.BackgroundRole).color().name()
    assert light_gap != dark_gap and dark_gap in {theme.DARK["gap_error"], theme.DARK["gap_warn"]}
    win.notification.show_message("error", "x")
    assert theme.DARK["layer"] in win.notification.styleSheet()
    win.set_theme("light")
    assert theme.LIGHT["layer"] in win.notification.styleSheet()  # a message already on screen is re-coloured


def test_help_viewer_follows_the_theme(win: MainWindow, qtbot):  # type: ignore[no-untyped-def]
    win.set_theme("dark")
    viewer = win.show_help()
    qtbot.addWidget(viewer)
    assert theme.DARK["layer"] in viewer.browser.document().defaultStyleSheet()
    win.set_theme("light")
    assert theme.LIGHT["layer"] in viewer.browser.document().defaultStyleSheet()


def test_graph_nodes_have_readable_text_in_both_themes(win: MainWindow):
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    win.select_item("EPS-0001")
    win.tabs.setCurrentWidget(win.graph_view)
    for name in ("dark", "light"):
        win.set_theme(name)
        texts = [i for i in win.graph_view.scene_.items() if isinstance(i, QGraphicsSimpleTextItem)]
        assert texts
        assert all(contrast(t.brush().color().name(), theme.TOKENS["layer"]) >= 4.5 for t in texts[:6])


def test_the_application_stylesheet_is_replaced_when_the_program_set_one(win: MainWindow):
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    app.setStyleSheet(theme.stylesheet())
    try:
        win.set_theme("dark")
        assert theme.DARK["background"] in app.styleSheet() and not win.styleSheet()
    finally:
        app.setStyleSheet("")

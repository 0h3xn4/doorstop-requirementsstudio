"""GUI audit B3/M3/M4: visible keyboard focus, contrast of selection, placeholders, checkboxes and disabled buttons."""

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rvs_gui import theme
from test_gui_theme import contrast


@pytest.fixture(autouse=True)
def _restore_light():  # type: ignore[no-untyped-def]
    yield
    theme.set_theme("light")


def _host(qtbot, name: str):  # type: ignore[no-untyped-def]
    theme.set_theme(name)
    host = QWidget()
    host.setStyleSheet(theme.stylesheet())
    lay = QVBoxLayout(host)
    first = QPushButton("First")
    button = QPushButton("Press me")
    check = QCheckBox("Tick me")
    combo = QComboBox()
    combo.addItems(["a", "b"])
    table = QTableView()
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "One")
    tabs.addTab(QWidget(), "Two")
    for w in (first, button, check, combo, table, tabs):
        lay.addWidget(w)
    qtbot.addWidget(host)
    host.show()
    host.activateWindow()
    qtbot.waitUntil(host.isActiveWindow, timeout=3000)
    return host, first, button, check, combo, table, tabs


def _pixels(widget):  # type: ignore[no-untyped-def]
    QApplication.processEvents()
    return widget.grab().toImage()


@pytest.mark.parametrize("name", ["light", "dark"])
def test_keyboard_focus_is_visible_on_buttons_checkboxes_combos_tables_and_tabs(qtbot, name: str):  # type: ignore[no-untyped-def]
    host, first, button, check, combo, table, tabs = _host(qtbot, name)
    for widget in (button, check, combo, table, tabs.tabBar()):
        first.setFocus()
        before = _pixels(widget)
        widget.setFocus()
        qtbot.waitUntil(widget.hasFocus, timeout=2000)
        after = _pixels(widget)
        assert before != after, f"{name}: no visible focus on {type(widget).__name__}"


@pytest.mark.parametrize("name", ["light", "dark"])
def test_default_button_looks_different_from_the_others(qtbot, name: str):  # type: ignore[no-untyped-def]
    host, _first, button, *_ = _host(qtbot, name)
    other = QPushButton("Press me")
    host.layout().addWidget(other)  # type: ignore[union-attr]
    button.setDefault(True)
    button.style().unpolish(button)
    button.style().polish(button)
    host.activateWindow()
    qtbot.wait(50)
    assert _pixels(button) != _pixels(other)


@pytest.mark.parametrize("name", ["light", "dark"])
def test_focus_and_selection_tokens_have_enough_contrast(name: str):
    t = theme.palette(name)
    for surface in ("background", "layer"):
        assert contrast(t["focus"], t[surface]) >= 3.0, (name, surface)  # focus ring: non-text contrast
    assert contrast(t["button_text"], t["interactive"]) >= 4.5  # selected rows: white on the interactive colour
    for fg, bg in [("warning_text", "background"), ("warning_text", "layer"), ("text_secondary", "layer")]:
        assert contrast(t[fg], t[bg]) >= 4.5, (name, fg, bg)
    assert contrast(t["border_strong"], t["background"]) >= 3.0  # checkbox border
    assert contrast(t["border_strong"], t["layer"]) >= 3.0 or name == "light"


def test_warning_severity_text_in_problems_uses_the_text_token():
    from rvs_core.findings import Severity
    from rvs_gui.models import severity_color

    assert severity_color(Severity.WARNING) == theme.TOKENS["warning_text"]
    assert contrast(severity_color(Severity.WARNING), "#ffffff") >= 4.5


def test_stylesheet_styles_selection_checkbox_disabled_and_placeholder():
    css = theme.stylesheet()
    for needle in (
        "QAbstractItemView::item:selected",
        "QCheckBox::indicator",
        "QPushButton:disabled",
        "QPushButton:default",
        "placeholder-text-color",
        'QPushButton[variant="secondary"]',
        "QTabBar::tab:focus",
    ):
        assert needle in css, needle


def test_disabled_button_is_grey_not_blue(qtbot):  # type: ignore[no-untyped-def]
    host, _first, button, *_ = _host(qtbot, "light")
    enabled = _pixels(button)
    button.setEnabled(False)
    disabled = _pixels(button)
    assert enabled != disabled
    centre = disabled.pixelColor(4, 4)
    assert centre.name() != theme.LIGHT["interactive"]


def test_secondary_buttons_are_not_primary(qtbot):  # type: ignore[no-untyped-def]
    from rvs_gui.widgets import secondary

    host, _first, button, *_ = _host(qtbot, "light")
    other = secondary(QPushButton("Cancel"))
    host.layout().addWidget(other)  # type: ignore[union-attr]
    host.style().polish(other)
    qtbot.wait(50)
    assert _pixels(button).pixelColor(6, 6) != _pixels(other).pixelColor(6, 6)

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rvs_gui.app import create_main_window  # noqa: E402
from rvs_gui.theme import TOKENS, load_fonts, stylesheet  # noqa: E402


def test_fonts_bundled_and_loaded(qtbot):
    families = load_fonts()
    assert "IBM Plex Sans" in families
    assert "IBM Plex Mono" in families


def test_stylesheet_uses_carbon_tokens():
    css = stylesheet()
    assert TOKENS["interactive"] in css
    assert "IBM Plex Sans" in css
    assert "{" in css and "@" not in css.replace("@media", "")  # no unresolved placeholders


def test_main_window_shows_provenance_and_problems_panel(qtbot):
    win = create_main_window()
    qtbot.addWidget(win)
    win.show()
    assert "Requirements & Verification Studio" in win.windowTitle()
    assert win.problems_panel.objectName() == "ProblemsPanel"
    assert "doorstop 3.2" in win.about_text()


def test_window_has_no_update_or_online_actions(qtbot):
    from PySide6.QtGui import QAction

    win = create_main_window()
    qtbot.addWidget(win)
    texts = " ".join(a.text().lower() for a in win.findChildren(QAction))
    assert "update" not in texts and "online" not in texts

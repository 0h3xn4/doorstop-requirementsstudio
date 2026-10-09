"""IBM Carbon (white theme) design tokens and Qt stylesheet. Fonts are bundled; nothing is fetched."""

from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication

# Carbon v11 tokens: white theme and g100 (dark). Every colour used by the GUI is a token, so a theme switch is just
# "replace the values and repaint". tests/test_gui_theme.py checks WCAG AA contrast of the text pairs in both.
LIGHT = {
    "background": "#ffffff",
    "layer": "#f4f4f4",
    "border": "#e0e0e0",
    "border_strong": "#8d8d8d",
    "text": "#161616",
    "text_secondary": "#525252",
    "interactive": "#0f62fe",
    "interactive_hover": "#0353e9",
    "button_text": "#ffffff",
    "link": "#0f62fe",
    "support_error": "#da1e28",
    "support_warning": "#f1c21b",
    "support_success": "#24a148",
    "warning_text": "#8e6a00",
    "header": "#161616",
    "header_text": "#f4f4f4",
    "gap_error": "#ffd7d9",
    "gap_warn": "#fcf4d6",
    "node_centre": "#d0e2ff",
    "diff_ins": "#198038",
    "diff_del": "#da1e28",
    "edge_parent": "#525252",
    "edge_verifies": "#24a148",
    "edge_satisfies": "#0f62fe",
    "edge_refines": "#8a3ffc",
    "edge_conflicts": "#da1e28",
}
DARK = {
    "background": "#161616",
    "layer": "#262626",
    "border": "#393939",
    "border_strong": "#8d8d8d",
    "text": "#f4f4f4",
    "text_secondary": "#c6c6c6",
    "interactive": "#0f62fe",
    "interactive_hover": "#0353e9",
    "button_text": "#ffffff",
    "link": "#78a9ff",
    "support_error": "#ff8389",
    "support_warning": "#f1c21b",
    "support_success": "#42be65",
    "warning_text": "#f1c21b",
    "header": "#000000",
    "header_text": "#f4f4f4",
    "gap_error": "#520408",
    "gap_warn": "#483700",
    "node_centre": "#002d9c",
    "diff_ins": "#42be65",
    "diff_del": "#ff8389",
    "edge_parent": "#a8a8a8",
    "edge_verifies": "#42be65",
    "edge_satisfies": "#78a9ff",
    "edge_refines": "#be95ff",
    "edge_conflicts": "#ff8389",
}
THEMES = ("light", "dark", "system")
TOKENS: dict[str, str] = dict(LIGHT)  # mutated in place by set_theme: importers keep seeing the current values


def palette(name: str) -> dict[str, str]:
    return DARK if name == "dark" else LIGHT


def system_scheme() -> str:
    """'dark' or 'light', as the desktop reports it (Qt 6.5+)."""
    app = QGuiApplication.instance()
    if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:  # type: ignore[attr-defined]
        return "dark"
    return "light"


def resolve(name: str) -> str:
    return system_scheme() if name == "system" else name


def set_theme(name: str) -> str:
    """Make ``name`` (light, dark or system) the current palette; returns the palette actually used."""
    if name not in THEMES:
        raise ValueError(f"Unknown theme '{name}'. Use light, dark or system.")
    used = resolve(name)
    TOKENS.clear()
    TOKENS.update(palette(used))
    return used


FONT_SANS = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"


_FONT_FAMILIES: list[str] | None = None


def load_fonts() -> list[str]:
    """Register the bundled IBM Plex fonts (once per process); return the family names now available.

    Applying the stylesheet before the fonts exist makes Qt search the system for the missing family on every widget
    (seconds per window), so every path that applies it loads the fonts first."""
    global _FONT_FAMILIES
    if _FONT_FAMILIES is not None:
        return list(_FONT_FAMILIES)
    families: list[str] = []
    for entry in sorted(resources.files("rvs_gui").joinpath("assets/fonts").iterdir(), key=lambda e: e.name):
        if entry.name.endswith((".woff", ".ttf", ".otf")):
            font_id = QFontDatabase.addApplicationFontFromData(entry.read_bytes())
            if font_id >= 0:
                families += QFontDatabase.applicationFontFamilies(font_id)
    _FONT_FAMILIES = sorted(set(families))
    return list(_FONT_FAMILIES)


def stylesheet() -> str:
    t = TOKENS
    return f"""
QWidget {{ font-family: "{FONT_SANS}"; font-size: 14px; color: {t["text"]}; background: {t["background"]}; }}
QMainWindow, QDockWidget {{ background: {t["layer"]}; }}
QMenuBar {{ background: {t["header"]}; color: {t["header_text"]}; }}
QMenuBar::item:selected {{ background: {t["interactive"]}; }}
QStatusBar {{ background: {t["layer"]}; color: {t["text_secondary"]}; border-top: 1px solid {t["border"]}; }}
QDockWidget::title {{ background: {t["layer"]}; padding: 6px 8px; border-bottom: 1px solid {t["border"]}; }}
QPushButton {{ background: {t["interactive"]}; color: {t["button_text"]}; border: none; padding: 10px 16px; }}
QPushButton:hover {{ background: {t["interactive_hover"]}; }}
QHeaderView::section {{ background: {t["layer"]}; border: none; border-bottom: 1px solid {t["border_strong"]};
    padding: 6px 8px; font-weight: 600; }}
QTableView, QTreeView {{ gridline-color: {t["border"]}; alternate-background-color: {t["layer"]}; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{ background: {t["layer"]};
    border: none; border-bottom: 1px solid {t["border_strong"]}; padding: 6px 8px; min-height: 22px; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {t["interactive"]}; }}
QLabel#Empty {{ color: {t["text_secondary"]}; background: transparent; }}
"""

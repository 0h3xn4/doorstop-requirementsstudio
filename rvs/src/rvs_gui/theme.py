"""IBM Carbon (white theme) design tokens and Qt stylesheet. Fonts are bundled; nothing is fetched."""

from importlib import resources

from PySide6.QtGui import QFontDatabase

# Carbon v11 white-theme tokens.
TOKENS = {
    "background": "#ffffff",
    "layer": "#f4f4f4",
    "border": "#e0e0e0",
    "border_strong": "#8d8d8d",
    "text": "#161616",
    "text_secondary": "#525252",
    "interactive": "#0f62fe",
    "interactive_hover": "#0353e9",
    "support_error": "#da1e28",
    "support_warning": "#f1c21b",
    "support_success": "#24a148",
    "header": "#161616",
    "header_text": "#f4f4f4",
}
FONT_SANS = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"


def load_fonts() -> list[str]:
    """Register the bundled IBM Plex fonts; return the family names now available."""
    families: list[str] = []
    for entry in sorted(resources.files("rvs_gui").joinpath("assets/fonts").iterdir(), key=lambda e: e.name):
        if entry.name.endswith((".woff", ".ttf", ".otf")):
            font_id = QFontDatabase.addApplicationFontFromData(entry.read_bytes())
            if font_id >= 0:
                families += QFontDatabase.applicationFontFamilies(font_id)
    return sorted(set(families))


def stylesheet() -> str:
    t = TOKENS
    return f"""
QWidget {{ font-family: "{FONT_SANS}"; font-size: 14px; color: {t["text"]}; background: {t["background"]}; }}
QMainWindow, QDockWidget {{ background: {t["layer"]}; }}
QMenuBar {{ background: {t["header"]}; color: {t["header_text"]}; }}
QMenuBar::item:selected {{ background: {t["interactive"]}; }}
QStatusBar {{ background: {t["layer"]}; color: {t["text_secondary"]}; border-top: 1px solid {t["border"]}; }}
QDockWidget::title {{ background: {t["layer"]}; padding: 6px 8px; border-bottom: 1px solid {t["border"]}; }}
QPushButton {{ background: {t["interactive"]}; color: #ffffff; border: none; padding: 10px 16px; }}
QPushButton:hover {{ background: {t["interactive_hover"]}; }}
QHeaderView::section {{ background: {t["layer"]}; border: none; border-bottom: 1px solid {t["border_strong"]};
    padding: 6px 8px; font-weight: 600; }}
QTableView, QTreeView {{ gridline-color: {t["border"]}; alternate-background-color: {t["layer"]}; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{ background: {t["layer"]};
    border: none; border-bottom: 1px solid {t["border_strong"]}; padding: 6px 8px; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {t["interactive"]}; }}
QLabel#Empty {{ color: {t["text_secondary"]}; background: transparent; }}
"""

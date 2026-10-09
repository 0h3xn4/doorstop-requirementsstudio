"""The bundled user guide, read from local files only (no browser, no network)."""

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from rvs_core.guide import guide_path
from rvs_gui.theme import TOKENS

MISSING = (
    "<h2>User guide not found</h2><p>This installation has no built user guide. "
    "Run <code>python scripts/build_guide.py</code> or reinstall the application.</p>"
)


def guide_css() -> str:
    """Colours for the guide (the page only sets layout), from the current theme."""
    t = TOKENS
    return (
        f"body {{ color: {t['text']}; background-color: {t['background']}; }} "
        f"h1 {{ border-bottom: 1px solid {t['border']}; }} "
        f"code {{ background-color: {t['layer']}; }} pre {{ background-color: {t['layer']}; }} "
        f"th {{ background-color: {t['border']}; }} td {{ border-top: 1px solid {t['border']}; }} "
        f"a {{ color: {t['link']}; }}"
    )


class HelpViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RVS user guide")
        self.resize(960, 720)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._clicked)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.browser)
        self._guide = guide_path()
        self.restyle()

    def restyle(self) -> None:
        """Re-render with the colours of the current theme (keeps the section being read)."""
        self.browser.document().setDefaultStyleSheet(guide_css())
        if self._guide is None:
            self.browser.setHtml(MISSING)
            return
        url = self.browser.source() if not self.browser.source().isEmpty() else QUrl.fromLocalFile(str(self._guide))
        position = self.browser.verticalScrollBar().value()
        self.browser.setSource(url)
        self.browser.reload()
        self.browser.verticalScrollBar().setValue(position)

    def show_section(self, anchor: str = "") -> None:
        if self._guide is None:
            return
        url = QUrl.fromLocalFile(str(self._guide))
        if anchor:
            url.setFragment(anchor)
        self.browser.setSource(url)

    def _clicked(self, url: QUrl) -> None:
        if url.isLocalFile() or (url.scheme() == "" and self._guide is not None):
            if url.scheme() == "":
                resolved = QUrl.fromLocalFile(str(self._guide))
                resolved.setFragment(url.fragment())
                url = resolved
            self.browser.setSource(url)
        # anything else (an http link in a document, say) is ignored: the application never goes online

"""The bundled user guide, read from local files only (no browser, no network)."""

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from rvs_core.guide import guide_path

MISSING = (
    "<h2>User guide not found</h2><p>This installation has no built user guide. "
    "Run <code>python scripts/build_guide.py</code> or reinstall the application.</p>"
)


class HelpViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RVS user guide")
        self.resize(900, 700)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._clicked)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.browser)
        self._guide = guide_path()
        if self._guide is None:
            self.browser.setHtml(MISSING)
        else:
            self.browser.setSource(QUrl.fromLocalFile(str(self._guide)))

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

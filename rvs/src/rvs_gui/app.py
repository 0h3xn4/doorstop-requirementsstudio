"""Application bootstrap and the (still empty) main window."""

import sys
from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow, QMessageBox

import rvs_core
from rvs_gui.theme import load_fonts, stylesheet

TITLE = "Requirements & Verification Studio"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{TITLE} {rvs_core.__version__}")
        self.resize(1200, 800)
        empty = QLabel("Open or create a project to begin.")
        empty.setObjectName("Empty")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(empty)

        self.problems_panel = QDockWidget("Problems", self)
        self.problems_panel.setObjectName("ProblemsPanel")
        self.problems_panel.setWidget(QLabel("No findings."))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_panel)

        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(self, TITLE, self.about_text()))
        self.menuBar().addMenu("Help").addAction(about)
        self.statusBar().showMessage("")

    def about_text(self) -> str:
        return (
            f"{TITLE}\nrvs {rvs_core.__version__}\ndoorstop {rvs_core.framework_version()}\nOffline: no network access."
        )


def create_app(argv: Sequence[str]) -> QApplication:
    app = QApplication.instance() or QApplication(list(argv))
    assert isinstance(app, QApplication)
    load_fonts()
    app.setStyleSheet(stylesheet())
    return app


def create_main_window() -> MainWindow:
    return MainWindow()


def main() -> int:
    app = create_app(sys.argv)
    win = create_main_window()
    win.show()
    return app.exec()

"""Regenerate the guide's screenshots from the fictional example project (offscreen Qt; no real data involved).

    QT_QPA_PLATFORM=offscreen python scripts/build_screenshots.py

Writes PNGs to docs/guide/images and copies them next to the bundled guide. Not part of the test suite: pixels depend
on the platform's font rendering, so the images are committed rather than checked for freshness.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from rvs_core.examples.satellite import build_satellite_project  # noqa: E402
from rvs_gui.app import MainWindow, create_app  # noqa: E402
from rvs_gui.wizard import NewRequirementWizard  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "guide" / "images"
BUNDLED = ROOT / "src" / "rvs_core" / "guide" / "images"
WIDTH = 860  # fits the help viewer


def save(widget, name: str) -> None:  # type: ignore[no-untyped-def]
    QTest.qWait(300)  # let layouts settle before grabbing
    image = widget.grab().toImage()
    if image.width() > WIDTH:
        image = image.scaledToWidth(WIDTH, Qt.TransformationMode.SmoothTransformation)
    image.save(str(IMAGES / name))
    print(f"wrote {IMAGES / name}")


def main() -> int:
    os.environ["RVS_CONFIG_DIR"] = tempfile.mkdtemp()  # never touch the real preferences
    os.environ["LOGNAME"] = os.environ["USER"] = "analyst"  # shown in provenance lines
    _app = create_app(sys.argv)  # keep a reference: the QApplication must outlive the windows
    project = Path(tempfile.mkdtemp()) / "example"
    build_satellite_project(project)
    IMAGES.mkdir(parents=True, exist_ok=True)

    win = MainWindow()
    win.resize(1400, 960)
    win.show()
    win.open_project(project)
    win.doc_tree.select_document("EPS") if hasattr(win.doc_tree, "select_document") else None
    win.select_item("EPS-0001")
    save(win, "items-guided.png")

    wizard = NewRequirementWizard(win.session, win, document="EPS")
    wizard.resize(760, 560)
    wizard.check_parent(wizard.parent_candidates()[0])
    wizard.show()
    save(wizard, "wizard-where.png")
    wizard.next()
    wizard.statement.setPlainText("The EPS provides adequate power to the payload.")
    save(wizard, "wizard-statement.png")
    wizard.close()

    win.set_mode("expert")
    win.select_item("EPS-0002")
    save(win, "items-expert.png")
    win.set_mode("guided")

    for tab, name in ((win.vcm_view, "vcm.png"), (win.graph_view, "graph.png")):
        win.tabs.setCurrentWidget(tab)
        save(win, name)
    win.tabs.setCurrentIndex(0)
    win.set_theme("dark", remember=False)
    win.select_item("EPS-0001")
    save(win, "items-dark.png")

    BUNDLED.mkdir(parents=True, exist_ok=True)
    for old in BUNDLED.glob("*.png"):
        old.unlink()
    for png in IMAGES.glob("*.png"):
        shutil.copy2(png, BUNDLED / png.name)
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

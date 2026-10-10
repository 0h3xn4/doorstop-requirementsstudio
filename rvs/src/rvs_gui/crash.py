"""Unexpected errors: a plain message and a report file with no project content. Never a traceback on screen."""

import sys
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from rvs_core.diagnostics import save_crash_report


def _default_show(text: str) -> None:
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "Requirements & Verification Studio", text)
    else:
        print(text, file=sys.stderr)


def handle_exception(
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    tb: TracebackType | None,
    show: Callable[[str], None] | None = None,
) -> Path | None:
    """Save a content-free report and tell the user where it is. Returns the report path."""
    path = save_crash_report(exc_type, exc, tb)
    where = (
        f"A short report (error type and program locations only, no requirement text) was saved to:\n{path}"
        if path
        else "A report could not be saved."
    )
    (show or _default_show)(
        "Something unexpected went wrong. Your saved project files are intact; unsaved edits in the open editor "
        f"may need to be re-entered.\n\n{where}\n\nSend this file to the maintainers if the problem repeats."
    )
    return path


def install_excepthook() -> None:
    previous = sys.excepthook

    def hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc, tb)
            return
        handle_exception(exc_type, exc, tb)

    sys.excepthook = hook

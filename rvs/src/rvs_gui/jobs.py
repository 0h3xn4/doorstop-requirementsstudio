"""Run a function on the global thread pool and report back on the GUI thread (windows stay responsive)."""

import sys
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Signals(QObject):
    """Lives on the GUI thread, so its slots always run there (queued connection from the worker)."""

    done = Signal(object)
    failed = Signal(object)  # the exception

    def __init__(self, on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]) -> None:
        super().__init__()
        self._on_done, self._on_failed = on_done, on_failed
        self.done.connect(self._handle_done)
        self.failed.connect(self._handle_failed)

    @Slot(object)
    def _handle_done(self, value: object) -> None:
        _alive.discard(self)
        _job_finished()
        self._on_done(value)

    @Slot(object)
    def _handle_failed(self, error: object) -> None:
        _alive.discard(self)
        _job_finished()
        self._on_failed(error)  # type: ignore[arg-type]


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals) -> None:
        super().__init__()
        self._fn, self._signals = fn, signals

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - reported to the GUI thread, never printed as a traceback
            self._signals.failed.emit(exc)
        except BaseException as exc:  # noqa: BLE001 - e.g. SystemExit in a worker: still report, or the job never ends
            self._signals.failed.emit(RuntimeError(f"The background task stopped unexpectedly ({type(exc).__name__})."))
        else:
            self._signals.done.emit(result)


_alive: set[_Signals] = set()

# With Python's default 5 ms thread switch interval, a CPU-bound worker can starve the GUI thread while a window is
# visible (measured: a 20 ms timer fired twice in 0.7 s). A 0.1 ms interval keeps the event loop running (1 ms was not enough in practice); it is only
# lowered while a background job is active.
_FAST_SWITCH = 0.0001
_saved_interval: float | None = None


def _job_started() -> None:
    global _saved_interval
    if not _alive_count():
        _saved_interval = sys.getswitchinterval()
        sys.setswitchinterval(min(_saved_interval, _FAST_SWITCH))


def _job_finished() -> None:
    global _saved_interval
    if not _alive_count() and _saved_interval is not None:
        sys.setswitchinterval(_saved_interval)
        _saved_interval = None


def _alive_count() -> int:
    return len(_alive)


def run_in_background(
    fn: Callable[[], Any], on_done: Callable[[Any], None], on_failed: Callable[[Exception], None]
) -> None:
    """``fn`` runs on a pool thread; the callbacks run on the thread that called this function."""
    signals = _Signals(on_done, on_failed)
    _job_started()
    _alive.add(signals)
    QThreadPool.globalInstance().start(_Task(fn, signals))

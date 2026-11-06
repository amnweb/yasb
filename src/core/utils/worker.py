"""Work that runs off the GUI thread and answers on it."""

import logging
import threading
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal


class WorkerSignals(QObject):
    finished = pyqtSignal(object, str)


# Kept until their answer reaches the GUI thread, or it would be lost with them
_running: set[WorkerSignals] = set()


def run_in_worker(work: Callable[[], object], done: Callable[[object, str], None], failure: str) -> None:
    """Runs work on its own thread and gives done its result, or what went wrong, on the GUI thread."""

    signals = WorkerSignals()
    _running.add(signals)

    def answered(result: object, error: str) -> None:
        _running.discard(signals)
        done(result, error)

    signals.finished.connect(answered)

    def run() -> None:
        try:
            result, error = work(), ""
        except RuntimeError as problem:
            result, error = None, str(problem)
        except Exception:
            logging.exception(failure)
            result, error = None, failure
        try:
            signals.finished.emit(result, error)
        except RuntimeError:
            # YASB is exiting, and the signals are gone with it
            pass

    threading.Thread(target=run, daemon=True).start()

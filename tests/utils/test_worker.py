import threading
from typing import Any

from PyQt6.QtGui import QGuiApplication

from core.utils.worker import run_in_worker
from tests.support.qt import wait


def answer(work: Any) -> dict[str, Any]:
    """Runs work through run_in_worker and waits for its answer, noting the thread of each."""
    seen: dict[str, Any] = {}

    def recorded() -> object:
        seen["work thread"] = threading.get_ident()
        return work()

    def done(result: object, error: str) -> None:
        seen.update({"done thread": threading.get_ident(), "result": result, "error": error})

    run_in_worker(recorded, done, "The work failed")
    for _ in range(300):
        if "done thread" in seen:
            break
        wait(10)
    return seen


def test_the_work_runs_off_the_gui_thread_and_the_answer_comes_back_on_it(qapp: QGuiApplication):
    gui = threading.get_ident()
    seen = answer(lambda: 42)
    assert seen["work thread"] != gui
    assert seen["done thread"] == gui
    assert (seen["result"], seen["error"]) == (42, "")


def test_a_failure_is_answered_on_the_gui_thread_instead_of_raised(qapp: QGuiApplication):
    def fail() -> object:
        raise OSError("disk gone")

    seen = answer(fail)
    assert seen["done thread"] == threading.get_ident()
    assert (seen["result"], seen["error"]) == (None, "The work failed")

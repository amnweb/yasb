# pyright: reportPrivateUsage=false

import gc
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.qml_types import register_qml_types
from core.services.process import process as process_module
from core.services.process.process import Process
from tests.support.qt import wait

PYTHON = sys.executable


def python(code: str) -> list[str]:
    return [PYTHON, "-c", code]


def until(condition: Callable[[], Any], timeout_ms: int = 5000) -> None:
    for _ in range(timeout_ms // 10):
        if condition():
            return
        wait(10)
    assert condition()


@pytest.fixture
def make(qapp: QGuiApplication) -> Iterator[Callable[..., Process]]:
    made: list[Process] = []

    def create(**settings: Any) -> Process:
        process = Process()
        for name, value in settings.items():
            process.setProperty(name, value)
        made.append(process)
        return process

    yield create
    for process in made:
        if not sip.isdeleted(process):
            sip.delete(process)


def test_start_opens_the_program_with_its_arguments_and_leaves_it(
    make: Callable[..., Process], monkeypatch: pytest.MonkeyPatch
):
    opened: list[tuple[str, str | None, str | None]] = []

    def shell_open(file: str, parameters: str | None = None, directory: str | None = None) -> None:
        opened.append((file, parameters, directory))

    monkeypatch.setattr(process_module, "shell_open", shell_open)
    for command in (
        "taskmgr",
        "wt -p PowerShell",
        '"C:\\Program Files\\App\\app.exe" --new "a b"',
        ["wt", "-p", "My Profile"],
    ):
        process = make(command=command, workingDirectory="C:\\Work")
        process.start()
        assert not process.property("running")
    assert opened == [
        ("taskmgr", None, "C:\\Work"),
        ("wt", "-p PowerShell", "C:\\Work"),
        ("C:\\Program Files\\App\\app.exe", '--new "a b"', "C:\\Work"),
        ("wt", '-p "My Profile"', "C:\\Work"),
    ]


def test_a_command_line_keeps_its_quotes(make: Callable[..., Process]):
    # The curl case of issue 815: a quoted argument with spaces reaches the program whole
    line = f'"{PYTHON}" -c "import sys; print(sys.argv[1])" "Authorization: Bearer KEY"'
    for shell in (False, True):
        process = make(command=line, shell=shell)
        process.run()
        until(lambda: process.property("output"))
        assert process.property("output") == "Authorization: Bearer KEY"
        assert process.property("exitCode") == 0 and process.property("error") == ""


def test_a_list_passes_exact_arguments_and_json_is_parsed(make: Callable[..., Process]):
    process = make(
        command=python('import json, sys; print(json.dumps({"args": sys.argv[1:]}))') + ['a "b"', "c d"],
        format="json",
    )
    process.run()
    until(lambda: process.property("data"))
    assert process.property("data") == {"args": ['a "b"', "c d"]}


def test_a_failed_run_keeps_the_last_good_result(make: Callable[..., Process], tmp_path: Path):
    # One command whose output a file decides: good JSON, then not JSON, then a failure
    answer = tmp_path / "answer.txt"
    code = (
        "import sys; text = open(sys.argv[1]).read()\n"
        "if text == 'fail': sys.stderr.write('disk full\\n'); sys.exit(3)\n"
        "print(text)"
    )
    process = make(command=[*python(code), str(answer)], format="json")
    finished: list[int] = []
    process.finished.connect(finished.append)

    answer.write_text('{"ok": 1}')
    process.run()
    until(lambda: finished)
    assert process.property("data") == {"ok": 1} and process.property("output") == '{"ok": 1}'

    answer.write_text("not json")
    process.run()
    until(lambda: process.property("error"))
    assert process.property("error").startswith("The output is not JSON")
    assert process.property("data") == {"ok": 1} and process.property("output") == '{"ok": 1}'

    answer.write_text("fail")
    process.run()
    until(lambda: process.property("exitCode") == 3)
    assert process.property("error") == "Exited with code 3: disk full"
    assert process.property("data") == {"ok": 1}
    assert process.property("errorOutput").strip() == "disk full"


def test_a_finished_run_deletes_its_signals_on_the_gui_thread(make: Callable[..., Process]):
    # Left to the garbage collector, they would be deleted on whichever thread it runs, which Qt does not allow
    process = make(command=python("print(1)"))
    finished: list[int] = []
    process.finished.connect(finished.append)
    gc.collect()
    gc.disable()
    try:
        process.run()
        until(lambda: finished)
        wait(50)
        assert not [obj for obj in gc.get_objects() if isinstance(obj, process_module._RunSignals)]
    finally:
        gc.enable()


def test_each_json_line_arrives_as_it_is_printed(make: Callable[..., Process]):
    code = "import json, time\nfor n in range(3):\n    print(json.dumps({'n': n}), flush=True)\n    time.sleep(0.05)"
    process = make(command=python(code), format="jsonLines")
    received: list[Any] = []
    process.received.connect(received.append)
    process.run()
    until(lambda: len(received) == 3)
    assert received == [{"n": 0}, {"n": 1}, {"n": 2}]
    assert process.property("data") == {"n": 2}


def test_each_line_arrives_as_text_while_the_program_runs(make: Callable[..., Process]):
    code = "import time\nfor word in ('one', 'two'):\n    print(word, flush=True)\n    time.sleep(0.05)"
    process = make(command=python(code), format="lines")
    received: list[Any] = []
    process.received.connect(received.append)
    process.run()
    until(lambda: received == ["one", "two"])
    assert process.property("output") == "two"
    until(lambda: not process.property("running"))
    assert process.property("exitCode") == 0


def test_a_run_that_takes_too_long_is_stopped(make: Callable[..., Process]):
    process = make(command=python("import time; time.sleep(30)"), timeout=200)
    failed: list[str] = []
    process.failed.connect(failed.append)
    started = time.monotonic()
    process.run()
    until(lambda: failed)
    assert failed == ["Stopped after 200 ms"] and time.monotonic() - started < 5
    assert not process.property("running")


def test_a_program_that_cannot_start_says_so(make: Callable[..., Process]):
    process = make(command=["yasb-no-such-program.exe"], shell=False)
    process.run()
    until(lambda: process.property("error"))
    assert process.property("error").startswith("Could not start yasb-no-such-program.exe")
    assert not process.property("running")


def test_destroying_a_widget_kills_its_program_at_once(make: Callable[..., Process]):
    marker = "yasb-process-test-marker"
    process = make(command=python(f"import time; time.sleep(30)  # {marker}"))
    process.run()
    until(lambda: process.property("running"))
    handle = process._handle
    until(lambda: handle is not None and handle.process is not None)
    assert handle is not None and handle.process is not None
    pid = handle.process.pid
    started = time.monotonic()
    sip.delete(process)
    assert time.monotonic() - started < 1
    wait(200)
    tasks = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    assert str(pid) not in tasks


def test_a_run_never_overlaps_the_one_before_it(make: Callable[..., Process]):
    process = make(command=python("import time; time.sleep(0.3); print('tick')"), interval=60000)
    until(lambda: process.property("running"))
    handle = process._handle
    # A run while one is running is not a second run
    process.run()
    assert process._handle is handle
    until(lambda: process.property("output") == "tick")


def test_an_inactive_widget_does_not_poll(make: Callable[..., Process]):
    process = make(command=python("print('tick')"), interval=60000, active=False)
    wait(100)
    assert not process.property("running") and process.property("output") == ""
    process.setProperty("active", True)
    until(lambda: process.property("output") == "tick")


def test_runs_happen_off_the_gui_thread(make: Callable[..., Process], monkeypatch: pytest.MonkeyPatch):
    gui = threading.get_ident()
    threads: list[int] = []
    real_popen = subprocess.Popen

    def popen(*args: Any, **kwargs: Any) -> Any:
        threads.append(threading.get_ident())
        return real_popen(*args, **kwargs)

    real_loads = process_module.json.loads

    def loads(text: str) -> Any:
        threads.append(threading.get_ident())
        return real_loads(text)

    monkeypatch.setattr(process_module.subprocess, "Popen", popen)
    monkeypatch.setattr(process_module.json, "loads", loads)
    process = make(command=python("print('[1]')"), format="json")
    process.run()
    until(lambda: process.property("data") == [1])
    # Starting the program and parsing its output both happened on another thread
    assert len(threads) == 2 and gui not in threads


def test_qml_widgets_use_it_with_a_list_command(qapp: QGuiApplication):
    register_qml_types()
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    source = f"""
        import QtQml
        import Yasb
        QtObject {{
            property Process proc: Process {{
                command: [{PYTHON!r}, "-c", "print('[1, 2, 3]')"]
                format: "json"
                Component.onCompleted: run()
            }}
            property int total: proc.data ? proc.data.reduce((sum, n) => sum + n, 0) : 0
        }}
    """
    component.setData(source.encode(), QUrl())
    item = component.create()
    assert item is not None, [error.toString() for error in component.errors()]
    until(lambda: item.property("total") == 6)
    sip.delete(item)


def test_a_bad_setting_ends_the_run_instead_of_leaving_it_running(make: Callable[..., Process]):
    unknown = make(command=python("print(1)"), encoding="no-such-encoding")
    unknown.run()
    until(lambda: unknown.property("error"))
    assert unknown.property("error") == "Unknown encoding no-such-encoding" and not unknown.property("running")

    # Windows takes no NUL in a command, which Python reports as a ValueError, not an OSError
    broken = make(command=[PYTHON, "-c", "print(1)\0"])
    broken.run()
    until(lambda: broken.property("error"))
    assert broken.property("error").startswith("Could not run") and not broken.property("running")
    # It is not stuck: it runs again
    failures: list[str] = []
    broken.failed.connect(failures.append)
    broken.run()
    until(lambda: failures)


def test_a_program_that_reads_its_input_ends_when_its_whole_output_is_wanted(make: Callable[..., Process]):
    process = make(command=python("import sys; print(len(sys.stdin.read()))"), timeout=5000)
    process.run()
    until(lambda: process.property("output") == "0" or process.property("error"))
    assert process.property("output") == "0" and process.property("error") == ""


def test_output_keeps_its_layout_without_windows_line_endings(make: Callable[..., Process]):
    process = make(command=python("print('  a | b'); print('  c | d')"))
    process.run()
    until(lambda: process.property("output"))
    assert process.property("output") == "  a | b\n  c | d"


def test_a_quoted_program_that_cannot_start_is_named_whole(make: Callable[..., Process]):
    process = make(command=r'"C:\No Such Folder\tool.exe" --flag', shell=False)
    process.run()
    until(lambda: process.property("error"))
    assert process.property("error").startswith(r"Could not start C:\No Such Folder\tool.exe:")

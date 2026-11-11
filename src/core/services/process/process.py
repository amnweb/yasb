"""Process, the QML type that runs a program or command line for a widget and gives what it printed, as text, as
JSON, or line by line while it runs.

A JSON API polled every ten minutes while the widget shows:

    Process {
        id: ip
        command: 'curl.exe -s -H "Authorization: Bearer KEY" https://api.ipinfo.io/lite/me'
        format: "json"
        interval: 600000
        active: widget.visible
    }
    Text { text: ip.data?.country ?? (ip.error ? "offline" : "...") }

A program that keeps running, one line at a time; a list runs it without cmd.exe, so kill() stops it:

    Process {
        command: ["ping", "-t", "example.com"]
        format: "lines"
        Component.onCompleted: run()
        onReceived: line => console.log(line)
    }

A command run on demand, through cmd.exe so pipes work:

    Process { id: address; command: 'ipconfig | findstr /c:"IPv4"' }
    Button { text: address.running ? "..." : address.output || "My address"; onClicked: address.run() }

An app opened and left to run, without waiting for it or reading what it prints:

    Process { id: terminal; command: "wt -p PowerShell" }
    Button { onClicked: terminal.start() }

Stopping a program does not stop the programs it started: a command run through cmd.exe that never ends keeps
running after cmd.exe is stopped, so long-running commands should be a list.
"""

import codecs
import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from io import BufferedReader
from typing import Any, cast

from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QObject, QTimer, QVariant, pyqtProperty, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.utils.shell_utils import shell_open

# text and json give the whole output once a run ends; lines and jsonLines give each line as it is printed
FORMATS = ("text", "json", "lines", "jsonLines")
STREAMS = ("lines", "jsonLines")
# A runaway program cannot fill YASB's memory: past this, it is stopped
MAX_OUTPUT = 16 * 1024 * 1024
MAX_ERROR_OUTPUT = 1024 * 1024
# How long a run waits for its output after its program ended. A program it started can keep the output open.
DRAIN_SECONDS = 0.5

type Command = str | tuple[str, ...]


def decode(data: bytes, encoding: str) -> str:
    """Text in the given encoding; without one, UTF-8, or else the console code page most Windows tools write."""
    if encoding:
        return data.decode(encoding, errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("oem", errors="replace")


def program_name(command: Command) -> str:
    if isinstance(command, tuple):
        return command[0] if command else ""
    line = command.strip()
    return line[1:].split('"', 1)[0] if line.startswith('"') else line.split(" ", 1)[0]


def command_line(command: Command, shell: bool) -> str | list[str]:
    """What to start. A string goes to Windows as typed, and each program reads its own arguments from it."""
    if isinstance(command, tuple):
        return list(command)
    if shell:
        # /d skips AutoRun scripts; with /s, cmd removes just the outer quotes and keeps the command as typed
        return f'"{os.environ.get("ComSpec", "cmd.exe")}" /d /s /c "{command}"'
    return command


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    error: str
    # QVariants made on the run's thread, so the GUI thread does not convert a large result
    output: Any = ""
    error_output: str = ""
    data: Any = None


class _Handle:
    """A run's program, which the GUI thread can stop before or after its thread has started it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.process: subprocess.Popen[bytes] | None = None
        self.reason = ""

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self.process = process
            stopped = bool(self.reason)
        if stopped:
            process.kill()

    def stop(self, reason: str) -> None:
        with self._lock:
            self.reason = self.reason or reason
            process = self.process
        if process is not None:
            try:
                process.kill()
            except OSError:
                # It has ended already
                pass


def _run(settings: dict[str, Any], handle: _Handle, line: Any, done: Any) -> None:
    """One run, on a daemon thread: line(value) for each line of a stream, then done(Outcome), always."""
    try:
        outcome = _start(settings, handle, line)
    except Exception as problem:
        logging.exception("Command %r failed", settings["command"])
        handle.stop(str(problem))
        outcome = Outcome(-1, f"Could not run {program_name(settings['command'])}: {problem}")
    done(outcome)


def _start(settings: dict[str, Any], handle: _Handle, line: Any) -> Outcome:
    command, form, encoding, timeout = (
        settings["command"],
        settings["format"],
        settings["encoding"],
        settings["timeout"],
    )
    stream = form in STREAMS
    if encoding:
        try:
            codecs.lookup(encoding)
        except LookupError:
            return Outcome(-1, f"Unknown encoding {encoding}")
    try:
        process = subprocess.Popen(
            command_line(command, settings["shell"]),
            # No input, so a program that reads its input ends instead of waiting for it
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=settings["workingDirectory"] or None,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError as problem:
        return Outcome(-1, f"Could not start {program_name(command)}: {problem.strerror or problem}")
    handle.attach(process)
    output, errors = bytearray(), bytearray()

    def read_output(pipe: BufferedReader) -> None:
        # A line is read at most one byte past the limit, so one endless line cannot fill memory
        while chunk := pipe.readline(MAX_OUTPUT + 1) if stream else pipe.read1(65536):
            if len(output) + len(chunk) > MAX_OUTPUT:
                handle.stop(f"Printed more than {MAX_OUTPUT // (1024 * 1024)} MB")
                return
            if not stream:
                output.extend(chunk)
                continue
            text = decode(chunk, encoding).rstrip("\r\n")
            if form == "lines":
                line(text)
            elif text.strip():
                try:
                    line(QVariant(json.loads(text)))
                except ValueError as problem:
                    line(ValueError(f"A line is not JSON: {problem}"))

    def read_errors(pipe: BufferedReader) -> None:
        # Read to the end, so the program never waits on a full pipe, and keep the start
        while chunk := pipe.read1(65536):
            errors.extend(chunk[: max(0, MAX_ERROR_OUTPUT - len(errors))])

    readers = [
        threading.Thread(target=read_output, args=(cast(BufferedReader, process.stdout),), daemon=True),
        threading.Thread(target=read_errors, args=(cast(BufferedReader, process.stderr),), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        exit_code = process.wait(timeout / 1000 if timeout > 0 else None)
    except subprocess.TimeoutExpired:
        handle.stop(f"Stopped after {timeout} ms")
        exit_code = process.wait()
    for reader in readers:
        reader.join(DRAIN_SECONDS)

    error = handle.reason
    error_text = decode(bytes(errors), encoding).replace("\r\n", "\n")
    if not error and exit_code != 0:
        first = error_text.strip().splitlines()
        error = f"Exited with code {exit_code}" + (f": {first[0]}" if first else "")
    if error or stream:
        return Outcome(exit_code, error, "", error_text)
    text = decode(bytes(output), encoding).replace("\r\n", "\n").rstrip("\n")
    data = None
    if form == "json":
        try:
            data = QVariant(json.loads(text))
        except ValueError as problem:
            return Outcome(exit_code, f"The output is not JSON: {problem}", "", error_text)
    return Outcome(exit_code, "", QVariant(text), error_text, data)


class _RunSignals(QObject):
    line = pyqtSignal(object)
    done = pyqtSignal(object)


# Kept until their run's end reaches the GUI thread: a run's threads emit only on these, never on the Process,
# which can be deleted while they run
_running: set[_RunSignals] = set()


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(owner: Process) -> Any:
        return owner.settings[name]

    def set_value(owner: Process, value: Any) -> None:
        owner.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class Process(QObject):
    """Runs a program and gives what it printed. See the examples at the top of this file."""

    settingsChanged = pyqtSignal()
    changed = pyqtSignal()
    # Each line as it is printed, with format lines as text and with jsonLines parsed
    received = pyqtSignal("QVariant")
    finished = pyqtSignal(int)
    failed = pyqtSignal(str)

    # A command line, run as typed, or a list of the program and its arguments
    command = _setting("QVariant", "command", settingsChanged)
    # Whether a command line runs through cmd.exe, for pipes and built-ins like echo
    shell = _setting(bool, "shell", settingsChanged)
    workingDirectory = _setting(str, "workingDirectory", settingsChanged)
    # Milliseconds between runs; 0 runs only on run()
    interval = _setting(int, "interval", settingsChanged)
    # Whether runs repeat on the interval; false pauses them, such as while the widget is hidden
    active = _setting(bool, "active", settingsChanged)
    # Milliseconds a run may take before it is stopped; 0 for no limit
    timeout = _setting(int, "timeout", settingsChanged)
    # text or json, the whole output once a run ends, or lines or jsonLines, each line as it is printed
    format = _setting(str, "format", settingsChanged)
    # The output's encoding, such as utf-8 or cp1252; empty tries UTF-8, then the console code page
    encoding = _setting(str, "encoding", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings: dict[str, Any] = {
            "command": "",
            "shell": True,
            "workingDirectory": "",
            "interval": 0,
            "active": True,
            "timeout": 0,
            "format": "text",
            "encoding": "",
        }
        self._output: Any = ""
        self._error_output = ""
        self._data: Any = None
        self._exit_code = 0
        self._error = ""
        self._last_run = 0
        self._duration = 0
        self._started = 0.0
        self._handle: _Handle | None = None
        # Answers from an earlier run are dropped
        self._run_number = 0
        # Between runs; started at 0 first, once QML has set the settings
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._timer.start(0)
        # A lambda, as an object's own methods are not called for its destroyed signal
        self.destroyed.connect(lambda: Process._halt(self))
        if (app := QCoreApplication.instance()) is not None:
            app.aboutToQuit.connect(self._halt)

    def change_setting(self, name: str, value: Any) -> None:
        if name == "command" and not isinstance(value, str):
            # A QML list arrives as a list or a QJSValue
            value = tuple(str(part) for part in (value.toVariant() if hasattr(value, "toVariant") else value))
        if value == self.settings[name]:
            return
        self.settings[name] = value
        self.settingsChanged.emit()
        if name in ("interval", "active"):
            self._timer.start(0)

    def _tick(self) -> None:
        if self.settings["active"] and self.settings["interval"] > 0:
            self.run()

    @qml_property("QVariant", notify=changed)
    def output(self) -> Any:
        return self._output

    @qml_property(str, notify=changed)
    def errorOutput(self) -> str:
        return self._error_output

    # The output parsed, with format json or jsonLines
    @qml_property("QVariant", notify=changed)
    def data(self) -> Any:
        return self._data

    @qml_property(int, notify=changed)
    def exitCode(self) -> int:
        return self._exit_code

    @qml_property(bool, notify=changed)
    def running(self) -> bool:
        return self._handle is not None

    # What went wrong in the last run; empty when it went well. A run that went wrong keeps the last good output.
    @qml_property(str, notify=changed)
    def error(self) -> str:
        return self._error

    # When the last run started, in milliseconds since the epoch, and how long it took
    @qml_property(float, notify=changed)
    def lastRun(self) -> float:
        return self._last_run

    @qml_property(int, notify=changed)
    def duration(self) -> int:
        return self._duration

    @pyqtSlot()
    def run(self) -> None:
        """Starts a run, unless one is running."""
        self._timer.stop()
        command = self.settings["command"]
        if self._handle is not None or not (command.strip() if isinstance(command, str) else command):
            return
        self._run_number += 1
        number = self._run_number
        handle = self._handle = _Handle()
        settings = {**self.settings, "command": command.strip() if isinstance(command, str) else command}
        if settings["format"] not in FORMATS:
            settings["format"] = "text"
        signals = _RunSignals()
        _running.add(signals)

        def on_line(value: Any) -> None:
            if sip.isdeleted(self):
                handle.stop("Stopped")
            else:
                self._on_line(number, value)

        def on_done(outcome: Outcome) -> None:
            _running.discard(signals)
            # Deleted on this thread once the run's end is handled; left to the garbage collector, it would be deleted
            # on whichever thread the collector runs, which Qt does not allow
            signals.deleteLater()
            if not sip.isdeleted(self):
                self._on_done(number, outcome)

        signals.line.connect(on_line)
        signals.done.connect(on_done)

        def line(value: Any) -> None:
            try:
                signals.line.emit(value)
            except RuntimeError:
                # YASB is exiting, and the signals are gone with it
                handle.stop("Stopped")

        def done(outcome: Outcome) -> None:
            try:
                signals.done.emit(outcome)
            except RuntimeError:
                pass

        try:
            threading.Thread(target=_run, args=(settings, handle, line, done), daemon=True).start()
        except RuntimeError:
            # Python takes no new threads while YASB exits
            _running.discard(signals)
            signals.deleteLater()
            self._handle = None
            return
        self._started = time.monotonic()
        self._last_run = int(time.time() * 1000)
        self.changed.emit()

    @pyqtSlot()
    def start(self) -> None:
        """Opens the program and leaves it running: no output, exit code or running state, as for an app."""
        command: Command = self.settings["command"]
        if isinstance(command, tuple):
            program, parameters = (command[0], subprocess.list2cmdline(command[1:])) if command else ("", "")
        else:
            line = command.strip()
            program = program_name(line)
            parameters = line[len(program) + 2 if line.startswith('"') else len(program) :].strip()
        if program:
            shell_open(program, parameters=parameters or None, directory=self.settings["workingDirectory"] or None)

    @pyqtSlot()
    def kill(self) -> None:
        if self._handle is not None:
            self._handle.stop("Stopped")

    def _on_line(self, number: int, value: Any) -> None:
        if number != self._run_number:
            return
        if isinstance(value, ValueError):
            self._error = str(value)
        elif self.settings["format"] == "lines":
            self._output = value
        else:
            self._data, self._error = value, ""
        self.changed.emit()
        if not isinstance(value, ValueError):
            self.received.emit(value)

    def _on_done(self, number: int, outcome: Outcome) -> None:
        if number != self._run_number:
            return
        self._handle = None
        self._exit_code = outcome.exit_code
        self._duration = int((time.monotonic() - self._started) * 1000)
        self._error_output = outcome.error_output
        self._error = outcome.error
        if not outcome.error and self.settings["format"] not in STREAMS:
            self._output = outcome.output
            if self.settings["format"] == "json":
                self._data = outcome.data
        if outcome.error:
            logging.debug("Command %r: %s", self.settings["command"], outcome.error)
        self.changed.emit()
        if outcome.error:
            self.failed.emit(outcome.error)
        else:
            self.finished.emit(outcome.exit_code)
        if self.settings["active"] and self.settings["interval"] > 0:
            self._timer.start(self.settings["interval"])

    def _halt(self) -> None:
        """Stops the run as the widget goes or YASB quits. Only touches Python state, as the object may be gone."""
        self._run_number += 1
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.stop("Stopped")

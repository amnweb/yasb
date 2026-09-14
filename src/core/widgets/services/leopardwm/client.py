"""Shared asynchronous CLI transport for LeopardWM workspace state."""

import json
import os

from PyQt6.QtCore import QCoreApplication, QObject, QProcess, QThread, QTimer, pyqtSignal

from core.widgets.services.leopardwm.state import SnapshotAssembler


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


class LeopardWMClient(QObject):
    state_changed = pyqtSignal(object)
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    MAX_FRAME_BYTES = 64 * 1024
    MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
    MAX_SNAPSHOT_FRAMES = 4096
    MAX_COMMANDS = 4
    _instances = {}

    @classmethod
    def acquire(cls, lwm_path: str):
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            raise RuntimeError("LeopardWMClient requires the Qt application thread")
        key = os.path.normcase(os.path.normpath(lwm_path))
        if key not in cls._instances:
            cls._instances[key] = cls(lwm_path, key)
        client = cls._instances[key]
        client._references += 1
        return client

    def __init__(self, lwm_path: str, key: str):
        super().__init__(QCoreApplication.instance())
        self.snapshot = None
        self.connected = False
        self.error_message = ""
        self._path = lwm_path
        self._key = key
        self._references = 0
        self._closed = False
        self._recovering = False
        self._backoff = 1000
        self._buffer = bytearray()
        self._stderr = bytearray()
        self._snapshot_bytes = 0
        self._snapshot_frames = 0
        self._assembler = SnapshotAssembler()
        self._commands = {}
        self._process = QProcess(self)
        self._process.setProgram(lwm_path)
        self._process.setArguments(["subscribe", "--events", "workspace_state"])
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._subscription_finished)
        self._process.errorOccurred.connect(self._subscription_error)
        self._reconnect_timer = self._timer(1000, self._start_subscription)
        self._heartbeat_timer = self._timer(45_000, lambda: self._fail("LeopardWM heartbeat timed out"))
        self._snapshot_timer = self._timer(10_000, lambda: self._fail("LeopardWM snapshot timed out"))
        QCoreApplication.instance().aboutToQuit.connect(self._on_quit)
        # Subscribers can attach their signals before the first process starts.
        QTimer.singleShot(0, self._start_subscription)

    def _timer(self, interval, callback):
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(interval)
        timer.timeout.connect(callback)
        return timer

    def _start_subscription(self):
        if self._closed or self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._recovering = False
        self._buffer.clear()
        self._stderr.clear()
        self._assembler.reset()
        self._snapshot_bytes = self._snapshot_frames = 0
        self._snapshot_timer.start(10_000)
        self._heartbeat_timer.start()
        self._process.start()

    def _read_stdout(self):
        # Yield between large batches to keep an initial snapshot from monopolizing Qt.
        self._process.setReadChannel(QProcess.ProcessChannel.StandardOutput)
        for _ in range(16):
            if not self._process.bytesAvailable():
                return
            data = bytes(self._process.read(self.MAX_FRAME_BYTES))
            if not self._closed and not self._recovering:
                self._consume_data(data)
        QTimer.singleShot(0, self._read_stdout)

    def _read_stderr(self):
        self._process.setReadChannel(QProcess.ProcessChannel.StandardError)
        while self._process.bytesAvailable():
            self._stderr.extend(bytes(self._process.read(4096)))
            del self._stderr[:-4096]
        self._process.setReadChannel(QProcess.ProcessChannel.StandardOutput)

    def _consume_data(self, data: bytes):
        if self._closed or self._recovering:
            return
        self._buffer.extend(data)
        try:
            while b"\n" in self._buffer:
                end = self._buffer.index(b"\n") + 1
                if end > self.MAX_FRAME_BYTES:
                    raise ValueError("LeopardWM frame exceeds 64 KiB")
                line = bytes(self._buffer[:end])
                del self._buffer[:end]
                event = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
                if not isinstance(event, dict):
                    raise ValueError("LeopardWM event must be an object")
                if event.get("type") == "workspace_snapshot_begin":
                    self._snapshot_bytes = self._snapshot_frames = 0
                    self._snapshot_timer.start(10_000)
                if self._assembler.in_progress or event.get("type") == "workspace_snapshot_begin":
                    self._snapshot_bytes += end
                    self._snapshot_frames += 1
                    if (
                        self._snapshot_bytes > self.MAX_SNAPSHOT_BYTES
                        or self._snapshot_frames > self.MAX_SNAPSHOT_FRAMES
                    ):
                        raise ValueError("LeopardWM snapshot exceeds client limits")
                snapshot = self._assembler.feed(event)
                self._heartbeat_timer.start()
                if snapshot is not None:
                    self._snapshot_timer.stop()
                    self.snapshot = snapshot
                    self.error_message = ""
                    self._backoff = 1000
                    if not self.connected:
                        self.connected = True
                        self.connection_changed.emit(True)
                    self.state_changed.emit(snapshot)
            # Exactly 64 KiB without newline cannot fit a valid frame.
            if len(self._buffer) >= self.MAX_FRAME_BYTES:
                raise ValueError("LeopardWM frame exceeds 64 KiB")
        except (ValueError, UnicodeError, RecursionError) as error:
            self._fail(str(error))

    def _report_error(self, message):
        self.error_message = message
        self.error_occurred.emit(message)

    def _offline(self):
        self._assembler.reset()
        self._buffer.clear()
        self._heartbeat_timer.stop()
        self._snapshot_timer.stop()
        if self.snapshot is not None:
            self.snapshot = None
            self.state_changed.emit(None)
        if self.connected:
            self.connected = False
            self.connection_changed.emit(False)

    def _fail(self, message):
        if self._closed or self._recovering:
            return
        self._recovering = True
        self._offline()
        self._report_error(message)
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
        else:
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        if not self._closed and not self._reconnect_timer.isActive():
            self._reconnect_timer.start(self._backoff)
            self._backoff = min(self._backoff * 2, 30_000)

    def _subscription_finished(self, *_):
        if self._closed:
            self._maybe_dispose()
            return
        self._read_stderr()
        if not self._recovering:
            detail = self._stderr.decode("utf-8", errors="replace").strip()
            self._fail(detail or "LeopardWM subscription disconnected")
        self._schedule_reconnect()

    def _subscription_error(self, error):
        if self._closed:
            self._maybe_dispose()
        elif error == QProcess.ProcessError.FailedToStart:
            self._fail(f"Cannot start LeopardWM CLI: {self._process.errorString()}")
        elif not self._recovering:
            self._fail(f"LeopardWM subscription error: {self._process.errorString()}")

    def activate_workspace(self, device_name: str, index: int):
        if self._closed or not self.connected or self.snapshot is None:
            return
        if type(index) is not int or not 0 <= index < 9:
            self._report_error("Invalid LeopardWM workspace index")
            return
        if device_name not in {monitor.device_name for monitor in self.snapshot.monitors}:
            self._report_error("LeopardWM monitor is no longer connected")
            return
        if len(self._commands) >= self.MAX_COMMANDS:
            self._report_error("Too many pending LeopardWM workspace commands")
            return
        process = QProcess(self)
        process.setProgram(self._path)
        process.setArguments(["workspace", str(index + 1), "--monitor", device_name])
        process.setStandardOutputFile(QProcess.nullDevice())
        process.setStandardErrorFile(QProcess.nullDevice())
        timer = self._timer(5000, lambda: self._command_timeout(process))
        self._commands[process] = timer
        process.finished.connect(lambda code, status: self._command_finished(process, code, status))
        process.errorOccurred.connect(lambda error: self._command_error(process, error))
        timer.start()
        process.start()

    def _command_timeout(self, process):
        if process not in self._commands:
            return
        if not self._closed:
            self._report_error("LeopardWM workspace command timed out")
        if process.state() == QProcess.ProcessState.NotRunning:
            self._remove_command(process)
        else:
            process.kill()

    def _command_error(self, process, error):
        if process not in self._commands:
            return
        if not self._closed:
            self._report_error(f"LeopardWM workspace command failed: {process.errorString()}")
        if error == QProcess.ProcessError.FailedToStart:
            self._remove_command(process)

    def _command_finished(self, process, code, status):
        if process not in self._commands:
            return
        if not self._closed and (code != 0 or status != QProcess.ExitStatus.NormalExit):
            self._report_error("LeopardWM workspace command failed")
        self._remove_command(process)

    def _remove_command(self, process):
        timer = self._commands.pop(process, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
            process.deleteLater()
        self._maybe_dispose()

    def release(self):
        if self._closed:
            return
        self._references -= 1
        if self._references <= 0:
            self._shutdown()

    def _shutdown(self):
        if self._closed:
            return
        self._closed = True
        self._instances.pop(self._key, None)
        self._reconnect_timer.stop()
        self._offline()
        for process, timer in tuple(self._commands.items()):
            timer.stop()
            if process.state() == QProcess.ProcessState.NotRunning:
                self._remove_command(process)
            else:
                process.kill()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
        self._maybe_dispose()

    def _maybe_dispose(self):
        if self._closed and not self._commands and self._process.state() == QProcess.ProcessState.NotRunning:
            try:
                QCoreApplication.instance().aboutToQuit.disconnect(self._on_quit)
            except TypeError, RuntimeError:
                pass
            self.deleteLater()

    def _on_quit(self):
        processes = [self._process, *self._commands]
        self._shutdown()
        # Qt's event loop is leaving; reap already-killed children before QObject teardown.
        for process in processes:
            if process.state() != QProcess.ProcessState.NotRunning:
                process.waitForFinished(1000)

import json
import logging
import threading
import uuid
from ctypes import Array, WinError, byref, c_char, create_string_buffer, string_at
from ctypes.wintypes import HANDLE
from typing import override

from PyQt6.QtCore import QThread, pyqtSignal

from core.services.komorebi.client import KomorebiClient
from core.utils.process import is_process_running
from core.utils.win32.bindings.kernel32 import (
    CancelIoEx,
    CloseHandle,
    ConnectNamedPipe,
    CreateEvent,
    CreateNamedPipe,
    GetLastError,
    GetOverlappedResult,
    ReadFileOverlapped,
    SetEvent,
    WaitForMultipleObjects,
)
from core.utils.win32.constants import (
    ERROR_BROKEN_PIPE,
    ERROR_IO_PENDING,
    ERROR_MORE_DATA,
    ERROR_PIPE_CONNECTED,
    FILE_FLAG_OVERLAPPED,
    INFINITE,
    INVALID_HANDLE_VALUE,
    PIPE_ACCESS_DUPLEX,
    PIPE_READMODE_MESSAGE,
    PIPE_TYPE_MESSAGE,
    PIPE_WAIT,
    WAIT_FAILED,
    WAIT_OBJECT_0,
)
from core.utils.win32.structs import OVERLAPPED

KOMOREBI_PIPE_BUFF_SIZE = 64 * 1024 * 8
KOMOREBI_PIPE_NAME = "yasb"


class KomorebiEventListener(QThread):
    # Komorebi's whole state after each event, and None once it disconnects
    state_changed = pyqtSignal(object)

    def __init__(self, pipe_name: str = KOMOREBI_PIPE_NAME, buffer_size: int = KOMOREBI_PIPE_BUFF_SIZE):
        super().__init__()
        self._komorebic = KomorebiClient()
        self._stop_event = threading.Event()
        self.pipe_name = f"{pipe_name}-{uuid.uuid1()}"
        self.buffer_size = buffer_size
        self.pipe: int | None = None
        # Pipe operations wait on _io_event and on _wake, which stop() sets, so the thread sleeps until one of them
        self._lock = threading.Lock()
        self._wake = 0
        self._io_event = 0

    def __str__(self):
        return "Komorebi Event Listener"

    @property
    def _app_running(self) -> bool:
        return not self._stop_event.is_set()

    def _create_pipe(self) -> None:
        open_mode = PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED
        pipe_mode = PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT
        max_instances = 1
        buffer_size_in = self.buffer_size
        buffer_size_out = self.buffer_size
        default_timeout_ms = 0
        security_attributes = None
        pipe = CreateNamedPipe(
            f"\\\\.\\pipe\\{self.pipe_name}",
            open_mode,
            pipe_mode,
            max_instances,
            buffer_size_in,
            buffer_size_out,
            default_timeout_ms,
            security_attributes,
        )
        if pipe == INVALID_HANDLE_VALUE:
            raise WinError(GetLastError())
        self.pipe = pipe
        logging.info("Created named pipe %s", self.pipe_name)

    def _close_pipe(self):
        if self.pipe:
            CloseHandle(self.pipe)
            self.pipe = None

    @override
    def run(self) -> None:
        with self._lock:
            # Manual-reset, so once stop() sets it every wait ends, even one that starts later
            self._wake = CreateEvent(None, True, self._stop_event.is_set(), None)
        self._io_event = CreateEvent(None, True, False, None)
        try:
            if self._wake and self._io_event:
                self._listen()
            else:
                logging.error(
                    "Could not create the events the komorebi listener waits on: %s", WinError(GetLastError())
                )
        finally:
            with self._lock:
                for handle in (self._wake, self._io_event):
                    if handle:
                        CloseHandle(handle)
                self._wake = self._io_event = 0

    def _listen(self) -> None:
        buffer = create_string_buffer(self.buffer_size)
        while self._app_running:
            should_reconnect = True
            try:
                self._create_pipe()
                self._wait_until_komorebi_online()
                pipe = self.pipe

                while self._app_running and pipe is not None:
                    try:
                        data = self._read_message(pipe, buffer)
                    except OSError as error:
                        # Komorebi closes the pipe when it quits
                        if error.winerror == ERROR_BROKEN_PIPE:
                            logging.info("Komorebi closed the named pipe %s", self.pipe_name)
                        else:
                            logging.error("Unexpected error occurred: %s", error)
                        break
                    if data is None:
                        break

                    if not data.strip():
                        continue

                    try:
                        event_message = json.loads(data.decode("utf-8"))
                        state = event_message["state"]

                        if event_message["event"] and state:
                            self.state_changed.emit(state)
                    except KeyError, ValueError:
                        logging.exception("Failed to parse komorebi state. Received data: %s", data)
            except BaseException, Exception:
                logging.exception("Komorebi has disconnected from the named pipe %s", self.pipe_name)
            finally:
                self._close_pipe()
                self.state_changed.emit(None)
                if not self._app_running:
                    should_reconnect = False
                elif should_reconnect:
                    logging.info("Attempting to reconnect to Komorebi...")
                    if self._stop_event.wait(3):
                        should_reconnect = False
            if not should_reconnect:
                break

    def stop(self):
        self._stop_event.set()
        with self._lock:
            if self._wake:
                SetEvent(self._wake)

    def _wait(self, pipe: int, overlapped: OVERLAPPED) -> bool:
        """Sleeps until the pipe operation completes, True, or stop() is called, False. A stopped operation is
        cancelled and has finished before this returns, as its OVERLAPPED and buffer must outlive it."""
        handles = (HANDLE * 2)(self._io_event, self._wake)
        result = WaitForMultipleObjects(2, handles, False, INFINITE)
        if result == WAIT_OBJECT_0:
            return True
        error = GetLastError() if result == WAIT_FAILED else 0
        CancelIoEx(pipe, byref(overlapped))
        GetOverlappedResult(pipe, byref(overlapped), True)
        if error:
            raise WinError(error)
        return False

    def _connect_pipe(self, pipe: int) -> bool:
        """Waits for komorebi to open the pipe; False when stop() came first."""
        overlapped = OVERLAPPED(hEvent=self._io_event)
        if ConnectNamedPipe(pipe, byref(overlapped)):
            return True
        error = GetLastError()
        # komorebi opened the pipe before this call
        if error == ERROR_PIPE_CONNECTED:
            return True
        if error != ERROR_IO_PENDING:
            raise WinError(error)
        if not self._wait(pipe, overlapped):
            return False
        ok, _ = GetOverlappedResult(pipe, byref(overlapped), False)
        if not ok:
            raise WinError(GetLastError())
        return True

    def _read_message(self, pipe: int, buffer: Array[c_char]) -> bytes | None:
        """The next message komorebi writes, or None when stop() came first. Raises ERROR_BROKEN_PIPE once komorebi
        closes the pipe."""
        chunks: list[bytes] = []
        while True:
            overlapped = OVERLAPPED(hEvent=self._io_event)
            if not ReadFileOverlapped(pipe, buffer, byref(overlapped)):
                error = GetLastError()
                if error == ERROR_IO_PENDING:
                    if not self._wait(pipe, overlapped):
                        return None
                elif error != ERROR_MORE_DATA:
                    raise WinError(error)
            ok, size = GetOverlappedResult(pipe, byref(overlapped), False)
            # A message longer than the buffer comes in parts, each but the last with ERROR_MORE_DATA
            if not ok and (error := GetLastError()) != ERROR_MORE_DATA:
                raise WinError(error)
            chunks.append(string_at(buffer, size))
            if ok:
                return b"".join(chunks)

    def _wait_until_komorebi_online(self):
        logging.debug("Waiting for Komorebi to subscribe to named pipe %s", self.pipe_name)
        warned = False
        while self._app_running:
            # Stays empty while komorebi isn't running, which is no fault, such as after quitting it
            error_message = ""
            if is_process_running("komorebi.exe"):
                stderr, proc = self._komorebic.wait_until_subscribed_to_pipe(self.pipe_name)
                if proc.returncode == 0:
                    break
                stderr_str = " ".join(stderr.decode("utf-8").replace("\n", " ").replace("\r", " ").split())
                if "(os error 10061)" not in stderr_str:
                    error_message = stderr_str
            if not warned:
                if error_message:
                    logging.warning("Komorebi failed to subscribe named pipe. %s", error_message)
                else:
                    logging.info("Komorebi is not running, YASB connects once it starts")
                warned = True
            if self._stop_event.wait(5):
                return

        if not self._app_running or self.pipe is None:
            return

        if not self._connect_pipe(self.pipe) or not self._app_running:
            return

        logging.info("Komorebi connected to named pipe: %s", self.pipe_name)
        state = self._komorebic.query_state()

        while self._app_running and state is None:
            logging.error(
                "Failed to retrieve komorebi state before starting event listener: None returned. "
                "Retrying in 2 second... Is komorebi online and its binaries added to $PATH?"
            )
            if self._stop_event.wait(2):
                return
            state = self._komorebic.query_state()

        if self._app_running:
            self.state_changed.emit(state)

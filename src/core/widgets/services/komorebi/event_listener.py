import json
import logging
import threading
import uuid
from ctypes import WinError
from typing import Any, override

from PyQt6.QtCore import QThread

from core.events.komorebi import KomorebiEvent
from core.events.service import EventService
from core.utils.process import is_process_running
from core.utils.win32.bindings.kernel32 import (
    CloseHandle,
    ConnectNamedPipe,
    CreateFile,
    CreateNamedPipe,
    GetLastError,
    PeekNamedPipe,
    ReadFile,
)
from core.utils.win32.constants import (
    ERROR_BROKEN_PIPE,
    ERROR_PIPE_CONNECTED,
    GENERIC_READ,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    PIPE_ACCESS_DUPLEX,
    PIPE_READMODE_MESSAGE,
    PIPE_TYPE_MESSAGE,
    PIPE_WAIT,
)
from core.widgets.services.komorebi.client import KomorebiClient

KOMOREBI_PIPE_BUFF_SIZE = 64 * 1024 * 8
KOMOREBI_PIPE_NAME = "yasb"


class KomorebiEventListener(QThread):
    def __init__(self, pipe_name: str = KOMOREBI_PIPE_NAME, buffer_size: int = KOMOREBI_PIPE_BUFF_SIZE):
        super().__init__()
        self._komorebic = KomorebiClient()
        self._stop_event = threading.Event()
        self.pipe_name = f"{pipe_name}-{uuid.uuid1()}"
        self.buffer_size = buffer_size
        self.event_service = EventService()
        self.pipe: int | None = None

    def __str__(self):
        return "Komorebi Event Listener"

    @property
    def _app_running(self) -> bool:
        return not self._stop_event.is_set()

    def _create_pipe(self) -> None:
        open_mode = PIPE_ACCESS_DUPLEX
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
        while self._app_running:
            should_reconnect = True
            try:
                self._create_pipe()
                self._wait_until_komorebi_online()
                pipe = self.pipe

                while self._app_running and pipe is not None:
                    ok, _, bytes_to_read = PeekNamedPipe(pipe)
                    if ok and not bytes_to_read:
                        if self._stop_event.wait(0.05):
                            break
                        continue

                    data = b""
                    if ok:
                        ok, data = ReadFile(pipe, bytes_to_read)
                    if not ok:
                        error = WinError(GetLastError())
                        if error.winerror == ERROR_BROKEN_PIPE:
                            logging.warning("Pipe has been ended: %s", error)
                            break
                        logging.error("Unexpected error occurred: %s", error)
                        continue

                    if not data.strip():
                        continue

                    try:
                        event_message = json.loads(data.decode("utf-8"))
                        event = event_message["event"]
                        state = event_message["state"]

                        if event and state:
                            self._emit_event(event, state)
                    except KeyError, ValueError:
                        logging.exception("Failed to parse komorebi state. Received data: %s", data)
            except BaseException, Exception:
                logging.exception("Komorebi has disconnected from the named pipe %s", self.pipe_name)
            finally:
                self._close_pipe()
                self.event_service.emit_event(KomorebiEvent.KomorebiDisconnect)
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
        client = CreateFile(f"\\\\.\\pipe\\{self.pipe_name}", GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
        if client != INVALID_HANDLE_VALUE:
            CloseHandle(client)

    def _emit_event(self, event: dict[str, Any] | str, state: dict[str, Any]) -> None:
        if isinstance(event, str):
            return
        self.event_service.emit_event(KomorebiEvent.KomorebiUpdate, event, state)

        if event["type"] in KomorebiEvent:
            self.event_service.emit_event(KomorebiEvent[event["type"]], event, state)

    def _wait_until_komorebi_online(self):
        logging.debug("Waiting for Komorebi to subscribe to named pipe %s", self.pipe_name)
        warned = False
        while self._app_running:
            error_message = "Komorebi is not running, please start Komorebi."
            if is_process_running("komorebi.exe"):
                stderr, proc = self._komorebic.wait_until_subscribed_to_pipe(self.pipe_name)
                if proc.returncode == 0:
                    break
                stderr_str = " ".join(stderr.decode("utf-8").replace("\n", " ").replace("\r", " ").split())
                if "(os error 10061)" not in stderr_str:
                    error_message = stderr_str
            if not warned:
                logging.warning("Komorebi failed to subscribe named pipe. %s", error_message)
                warned = True
            if self._stop_event.wait(5):
                return

        if not self._app_running or self.pipe is None:
            return

        if not ConnectNamedPipe(self.pipe):
            error = GetLastError()
            if error != ERROR_PIPE_CONNECTED and self._app_running:
                raise WinError(error)
        if not self._app_running:
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

        self.event_service.emit_event(KomorebiEvent.KomorebiConnect, state)

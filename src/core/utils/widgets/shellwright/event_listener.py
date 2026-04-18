"""
Shellwright named-pipe event listener.

shellwright creates a byte-mode server pipe at ``\\\\.\\pipe\\shellwright`` and
writes newline-terminated JSON state blobs whenever workspace or layout state
changes.  YASB connects as a read-only byte-stream client, accumulates bytes
until it sees a newline, then parses and emits the Qt event.

Pipe direction
--------------
* **shellwright** — ``CreateNamedPipeW(..., PIPE_ACCESS_OUTBOUND, PIPE_TYPE_BYTE)``
* **YASB**        — ``CreateFile(..., GENERIC_READ)``  (byte stream client)

Each JSON message looks like::

    {"monitors":{"elements":[{"name":"Monitor 1","index":0,"workspaces":{
      "elements":[{"name":"1","index":0,"layout":"fibonacci",
                   "focused_window":"Title","windows":{"elements":[],"focused":0}}],
      "focused":0}}],"focused":0}}\\n
"""

import json
import logging
import threading

import pywintypes
import win32file
from PyQt6.QtCore import QThread

from core.event_enums import ShellwrightEvent
from core.event_service import EventService

SHELLWRIGHT_PIPE_NAME = r"\\.\pipe\shellwright"
SHELLWRIGHT_READ_SIZE = 4096


class ShellwrightEventListener(QThread):
    def __init__(
        self,
        pipe_name: str = SHELLWRIGHT_PIPE_NAME,
        read_size: int = SHELLWRIGHT_READ_SIZE,
    ):
        super().__init__()
        self._stop_event = threading.Event()
        self.pipe_name = pipe_name
        self.read_size = read_size
        self.event_service = EventService()
        self._pipe = None

    def __str__(self) -> str:
        return "Shellwright Event Listener"

    @property
    def _app_running(self) -> bool:
        return not self._stop_event.is_set()

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self) -> bool:
        """Open shellwright's byte-mode pipe as a read-only client.

        Returns True on success.
        """
        try:
            self._pipe = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            logging.info("Connected to shellwright pipe %s", self.pipe_name)
            return True
        except pywintypes.error as e:
            # 2  = ERROR_FILE_NOT_FOUND  (shellwright not running)
            # 231 = ERROR_PIPE_BUSY      (server not yet accepting)
            if e.winerror not in (2, 231):
                logging.warning("Cannot open shellwright pipe: %s", e)
            return False

    def _close(self) -> None:
        if self._pipe is not None:
            try:
                win32file.CloseHandle(self._pipe)
            except Exception:
                pass
            self._pipe = None

    # ── Main thread ───────────────────────────────────────────────────────────

    def run(self) -> None:
        while self._app_running:
            # Wait until shellwright starts.
            while self._app_running and not self._connect():
                if self._stop_event.wait(3):
                    return

            if not self._app_running:
                break

            connected = False
            buf = b""
            _stopped = False

            try:
                while self._app_running:
                    try:
                        _, chunk = win32file.ReadFile(self._pipe, self.read_size)
                    except pywintypes.error as e:
                        if e.winerror in (109, 232, 6):
                            # 109 = ERROR_BROKEN_PIPE
                            # 232 = ERROR_NO_DATA
                            #   6 = ERROR_INVALID_HANDLE
                            logging.info("Shellwright pipe closed (winerr=%d)", e.winerror)
                        else:
                            logging.exception("Unexpected shellwright pipe error: %s", e)
                        break

                    if not chunk:
                        continue

                    buf += chunk

                    # A single ReadFile may contain multiple newline-terminated
                    # JSON objects — process all complete lines.
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            state = json.loads(line.decode("utf-8", errors="replace"))
                        except json.JSONDecodeError:
                            logging.warning(
                                "Shellwright: bad JSON: %r", line[:200]
                            )
                            continue

                        if not connected:
                            connected = True
                            self.event_service.emit_event(
                                ShellwrightEvent.ShellwrightConnect, state
                            )
                        else:
                            self.event_service.emit_event(
                                ShellwrightEvent.ShellwrightUpdate, state
                            )

            finally:
                self._close()
                self.event_service.emit_event(ShellwrightEvent.ShellwrightDisconnect)
                _stopped = not self._app_running

            if _stopped:
                break
            logging.info("Shellwright disconnected — retrying in 3 s")
            self._stop_event.wait(3)

    def stop(self) -> None:
        self._stop_event.set()
        self._close()

import ctypes
import logging
import os
import struct
import time

import pywintypes
import win32api
import win32event
import win32file
import win32pipe
import winerror
from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal

from core.widgets.services.systray.utils import (
    IconData,
    get_dll_path,
    get_explorer_pid,
    is_dll_loaded,
    validate_icon_data,
)
from core.utils.win32.bindings.kernel32 import (
    CloseHandle,
    CreateMutex,
    FreeLibrary,
    GetLastError,
    GetProcAddress,
    LoadLibraryW,
)
from core.utils.win32.bindings.user32 import (
    EnumWindows,
    GetClassName,
    GetWindowThreadProcessId,
    PostThreadMessage,
    SetWindowsHookEx,
    UnhookWindowsHookEx,
)
from core.utils.win32.constants import (
    NIF_GUID,
    NIM_ADD,
    NIM_DELETE,
    NIM_MODIFY,
    NIM_SETVERSION,
    WH_GETMESSAGE,
)
from core.utils.win32.structs import NOTIFYICONDATA, SHELLTRAYDATA

logger = logging.getLogger("systray_hook")


def _find_shell_tray_hwnd(explorer_pid: int) -> int:
    """Find the Shell_TrayWnd belonging to a specific Explorer PID. Returns 0 if not found."""
    _WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    result = 0

    @_WNDENUMPROC
    def _cb(hwnd, _):
        nonlocal result
        if GetClassName(hwnd) != "Shell_TrayWnd":
            return True
        pid = ctypes.c_ulong(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == explorer_pid:
            result = hwnd
            return False  # stop enumeration
        return True

    EnumWindows(_cb, 0)
    return result


def _inject_via_hook(dll_path: str, explorer_pid: int) -> int:
    """Inject dll_path into Explorer via SetWindowsHookEx (WH_GETMESSAGE).

    Returns the hook handle on success (caller must UnhookWindowsHookEx after pipe connects), 0 on failure.
    """
    h_dll = LoadLibraryW(dll_path)
    if not h_dll:
        logger.error("Failed to load DLL locally (err=%d)", GetLastError())
        return 0
    try:
        hook_proc = GetProcAddress(h_dll, b"GetMsgProc")
        if not hook_proc:
            logger.error("GetMsgProc not found in DLL")
            return 0
        hwnd = 0
        for _ in range(60):
            hwnd = _find_shell_tray_hwnd(explorer_pid)
            if hwnd:
                break
            time.sleep(0.05)
        if not hwnd:
            logger.error("Shell_TrayWnd not found")
            return 0
        tid = GetWindowThreadProcessId(hwnd, None)
        if not tid:
            logger.error("GetWindowThreadProcessId failed")
            return 0
        h_hook = SetWindowsHookEx(WH_GETMESSAGE, hook_proc, h_dll, tid)
        if not h_hook:
            logger.error("SetWindowsHookExW failed (err=%d)", GetLastError())
            return 0
        # Post WM_NULL so Explorer's thread dequeues a message and loads the DLL immediately.
        PostThreadMessage(tid, 0, 0, 0)
        return h_hook
    finally:
        FreeLibrary(h_dll)


WATCHDOG_MUTEX_NAME = "Global\\YASBTrayHookAlive"
MESSAGE_PIPE_NAME = r"\\.\pipe\yasb_systray_monitor"
PIPE_BUFFER_SIZE = 32 * 1024


class SystrayHook(QObject):
    update_icons = pyqtSignal()
    icon_modified = pyqtSignal(IconData)
    icon_deleted = pyqtSignal(IconData)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._h_mutex = None
        self._message_pipe = None
        self._h_hook: int = 0

        # Create the watchdog mutex — held for entire lifetime.
        try:
            self._h_mutex = CreateMutex(None, True, WATCHDOG_MUTEX_NAME)
        except pywintypes.error as e:
            logger.error("Failed to create watchdog mutex: %s", e)
            return

        # A message pipe that the DLL will connect to.
        # Using FILE_FLAG_OVERLAPPED for efficient waiting in a separate thread
        logger.debug("Creating pipe %s...", MESSAGE_PIPE_NAME)
        try:
            self._message_pipe = win32pipe.CreateNamedPipe(
                MESSAGE_PIPE_NAME,
                win32pipe.PIPE_ACCESS_INBOUND | win32file.FILE_FLAG_OVERLAPPED,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                1,
                PIPE_BUFFER_SIZE,
                PIPE_BUFFER_SIZE,
                0,
                None,
            )
        except pywintypes.error as e:
            logger.error("Failed to create pipe: %s", e)
            if self._h_mutex:
                CloseHandle(self._h_mutex)
                self._h_mutex = None
            return

    def destroy(self):
        """Clean up the hook"""
        self._running = False
        if self._h_hook:
            UnhookWindowsHookEx(self._h_hook)
            self._h_hook = 0
        if self._message_pipe is not None:
            # Closing the handle will also cancel any pending overlapped I/O in the worker thread
            win32api.CloseHandle(self._message_pipe)
            self._message_pipe = None
        if self._h_mutex is not None:
            CloseHandle(self._h_mutex)
            self._h_mutex = None

    def run(self) -> None:
        """Worker thread loop to handle pipe I/O"""
        if self._running:
            return

        if self._message_pipe is None:
            logger.error("Pipe not initialized")
            return

        self._running = True
        h_event = win32event.CreateEvent(None, True, False, None)
        overlapped = win32file.OVERLAPPED()
        overlapped.hEvent = h_event

        # Retry loop: retries in case or explorer restart or injection failure
        while self._running:
            pid = get_explorer_pid()
            if not pid:
                time.sleep(1)
                continue
            dll_path = get_dll_path()  # will hard crash if unsupported architecture
            dll_name = os.path.basename(dll_path)
            if not is_dll_loaded(pid, dll_name):
                logger.info("Injecting into Explorer (PID: %s)", pid)
                self._h_hook = _inject_via_hook(dll_path, pid)
                if not self._h_hook:
                    logger.error("Injection failed, retrying in 5s")
                    time.sleep(5)
                    continue
            try:
                logger.debug("Waiting for DLL to connect")
                win32event.ResetEvent(h_event)
                res = win32pipe.ConnectNamedPipe(self._message_pipe, overlapped)
                if res == winerror.ERROR_PIPE_CONNECTED:
                    pass
                elif res == winerror.ERROR_IO_PENDING:
                    while self._running:
                        # Non-blocking check for event signal
                        wait_res = win32event.WaitForSingleObject(h_event, 500)
                        if wait_res == win32event.WAIT_OBJECT_0:
                            break
                elif res == 0:
                    pass
                else:
                    raise pywintypes.error(res, "ConnectNamedPipe", "Unexpected error")

                if not self._running:
                    break

                logger.debug("DLL Connected")
                if self._h_hook:
                    UnhookWindowsHookEx(self._h_hook)
                    self._h_hook = 0
                self.update_icons.emit()

                buffer = win32file.AllocateReadBuffer(PIPE_BUFFER_SIZE)
                # Read loop: reads a single message from the explorer hook
                while self._running:
                    chunks: list[bytes] = []
                    read_error = False
                    # Chunks loop: collects chunks until the full message is received
                    while True:
                        win32event.ResetEvent(h_event)
                        try:
                            hr, _data = win32file.ReadFile(self._message_pipe, buffer, overlapped)
                        except pywintypes.error as e:
                            if e.winerror == winerror.ERROR_BROKEN_PIPE:
                                logger.debug("DLL Disconnected")
                            elif e.winerror == winerror.ERROR_OPERATION_ABORTED:
                                logger.debug("Pipe operation aborted (closing)")
                            else:
                                logger.error("ReadFile failed immediately: %s", e)
                            read_error = True
                            break

                        if hr == winerror.ERROR_IO_PENDING:
                            while self._running:
                                wait_res = win32event.WaitForSingleObject(h_event, 500)
                                if wait_res == win32event.WAIT_OBJECT_0:
                                    break
                            if not self._running:
                                break
                        # Retrieve completed result
                        try:
                            n_read = win32file.GetOverlappedResult(self._message_pipe, overlapped, True)
                            chunks.append(bytes(buffer[:n_read]))
                            break  # Full message received
                        except pywintypes.error as e:
                            if e.winerror == winerror.ERROR_MORE_DATA:
                                chunks.append(bytes(buffer[:PIPE_BUFFER_SIZE]))
                                continue  # More data remaining for this message
                            elif e.winerror == winerror.ERROR_BROKEN_PIPE:
                                logger.debug("DLL Disconnected")
                            else:
                                logger.error("GetOverlappedResult failed: %s", e)
                            read_error = True
                            break
                    if read_error or not self._running:
                        break
                    if chunks:
                        self.process_message(b"".join(chunks))
            except Exception as e:
                # Avoid logging error if shutting down
                if self._running:
                    logger.error("Worker error: %s", e)
            finally:
                try:
                    win32pipe.DisconnectNamedPipe(self._message_pipe)
                except pywintypes.error:
                    pass
            if self._running:
                time.sleep(3)
        win32api.CloseHandle(h_event)

    def process_message(self, data_bytes: bytes) -> None:
        """Processes a message from the explorer hook"""
        if len(data_bytes) < 4:
            return

        msg_type = struct.unpack_from("=I", data_bytes)[0]

        if msg_type == 1:
            msg = data_bytes[4:].decode("utf-8", errors="ignore")
            logger.debug(msg.strip())
        elif msg_type == 2:
            if len(data_bytes) < 28:
                logger.error("Invalid COPYDATA message size: %s", len(data_bytes))
                return

            header_fmt = "=IQIIII"  # type, dwData, cbData, iconWidth, iconHeight, iconDataSize
            header_size = struct.calcsize(header_fmt)
            _type, _dw_data, cb_data, icon_w, icon_h, icon_data_size = struct.unpack_from(header_fmt, data_bytes)

            # Payload
            cursor = header_size
            payload = data_bytes[cursor : cursor + cb_data]

            # Use ctypes to cast payload
            tray_message = SHELLTRAYDATA.from_buffer_copy(payload)
            icon_data: NOTIFYICONDATA = tray_message.icon_data

            # Icon
            icon = None
            if icon_data_size > 0:
                cursor += cb_data
                rgba_bytes = data_bytes[cursor : cursor + icon_data_size]
                icon = Image.frombuffer("RGBA", (icon_w, icon_h), rgba_bytes, "raw", "RGBA", 0, 1)  # type: ignore

            if tray_message.message_type in {NIM_ADD, NIM_MODIFY, NIM_SETVERSION}:
                validated_data = validate_icon_data(icon_data, icon)
                validated_data.message_type = tray_message.message_type
                self.icon_modified.emit(validated_data)
            elif tray_message.message_type == NIM_DELETE:
                self.icon_deleted.emit(
                    IconData(
                        hWnd=icon_data.hWnd,
                        uID=icon_data.uID,
                        guid=icon_data.guidItem.to_uuid() if icon_data.uFlags & NIF_GUID else None,
                    )
                )

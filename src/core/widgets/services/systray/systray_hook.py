import ctypes
import logging
import os
import struct
import time
from ctypes.wintypes import BOOL, DWORD, HWND, LPARAM
from threading import Event, Lock

from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal

from core.utils.win32.bindings.kernel32 import (
    CancelIoEx,
    CloseHandle,
    ConnectNamedPipe,
    CreateEvent,
    CreateMutex,
    CreateNamedPipe,
    DisconnectNamedPipe,
    FreeLibrary,
    GetLastError,
    GetOverlappedResult,
    GetProcAddress,
    LoadLibraryW,
    ReadFileOverlapped,
    ResetEvent,
    WaitForSingleObject,
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
    ERROR_BROKEN_PIPE,
    ERROR_IO_PENDING,
    ERROR_MORE_DATA,
    ERROR_OPERATION_ABORTED,
    ERROR_PIPE_CONNECTED,
    ERROR_SUCCESS,
    FILE_FLAG_OVERLAPPED,
    INVALID_HANDLE_VALUE,
    NIF_GUID,
    NIM_ADD,
    NIM_DELETE,
    NIM_MODIFY,
    NIM_SETVERSION,
    PIPE_ACCESS_INBOUND,
    PIPE_READMODE_MESSAGE,
    PIPE_TYPE_MESSAGE,
    PIPE_WAIT,
    WAIT_FAILED,
    WAIT_OBJECT_0,
    WH_GETMESSAGE,
)
from core.utils.win32.structs import NOTIFYICONDATA, OVERLAPPED, SHELLTRAYDATA
from core.widgets.services.systray.utils import (
    IconData,
    get_dll_path,
    get_explorer_pid,
    is_dll_loaded,
    validate_icon_data,
)

logger = logging.getLogger("systray_hook")


def _find_shell_tray_hwnd(explorer_pid: int) -> int:
    """Find the Shell_TrayWnd belonging to a specific Explorer PID. Returns 0 if not found."""
    _WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
    result = 0

    @_WNDENUMPROC
    def _cb(hwnd: int, _: int) -> bool:
        nonlocal result
        if GetClassName(hwnd) != "Shell_TrayWnd":
            return True
        pid = DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == explorer_pid:
            result = hwnd
            return False  # stop enumeration
        return True

    EnumWindows(ctypes.cast(_cb, ctypes.c_void_p), 0)
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
        self._worker_active = False
        self._state_lock = Lock()
        self._stop_event = Event()
        self._h_mutex: int | None = None
        self._message_pipe: int | None = None
        self._h_hook: int = 0

        # Create the watchdog mutex - held for entire lifetime.
        self._h_mutex = CreateMutex(None, True, WATCHDOG_MUTEX_NAME)
        if not self._h_mutex:
            logger.error("Failed to create watchdog mutex (err=%d)", GetLastError())
            self._h_mutex = None
            return

        # A message pipe that the DLL will connect to.
        # Using FILE_FLAG_OVERLAPPED for efficient waiting in a separate thread
        logger.debug("Creating pipe %s...", MESSAGE_PIPE_NAME)
        self._message_pipe = CreateNamedPipe(
            MESSAGE_PIPE_NAME,
            PIPE_ACCESS_INBOUND | FILE_FLAG_OVERLAPPED,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,
            PIPE_BUFFER_SIZE,
            PIPE_BUFFER_SIZE,
            0,
            None,
        )
        if not self._message_pipe or self._message_pipe == INVALID_HANDLE_VALUE:
            logger.error("Failed to create pipe (err=%d)", GetLastError())
            self._message_pipe = None
            CloseHandle(self._h_mutex)
            self._h_mutex = None

    def run(self) -> None:
        """Own the worker's I/O resources and retry sessions until shutdown."""
        with self._state_lock:
            if self._worker_active:
                return
            if self._message_pipe is None:
                logger.error("Pipe not initialized")
                return
            pipe = self._message_pipe
            self._stop_event.clear()
            self._running = True
            self._worker_active = True

        h_event = 0
        try:
            h_event = CreateEvent(None, True, False, None)
            if not h_event:
                logger.error("Failed to create pipe event (err=%d)", GetLastError())
                return
            buffer = ctypes.create_string_buffer(PIPE_BUFFER_SIZE)

            # Retry after Explorer restarts or injection fails.
            while self._running:
                if not self._ensure_injected():
                    continue
                self._run_pipe_session(pipe, h_event, buffer)
                self._stop_event.wait(3)
        finally:
            with self._state_lock:
                self._running = False
                self._unhook()
                CloseHandle(pipe)
                self._message_pipe = None
                self._worker_active = False
            if h_event:
                CloseHandle(h_event)

    def destroy(self):
        """Clean up the hook"""
        with self._state_lock:
            self._running = False
            self._stop_event.set()
            self._unhook()
            if self._message_pipe is not None:
                if self._worker_active:
                    # The worker drains cancellation before releasing its OVERLAPPED and buffer.
                    CancelIoEx(self._message_pipe)
                else:
                    CloseHandle(self._message_pipe)
                    self._message_pipe = None
            if self._h_mutex is not None:
                CloseHandle(self._h_mutex)
                self._h_mutex = None

    def _ensure_injected(self) -> bool:
        """Find Explorer and inject the DLL if needed, backing off on failure."""
        pid = get_explorer_pid()
        if not pid:
            self._stop_event.wait(1)
            return False
        if not self._running:
            return False

        dll_path = get_dll_path()  # Raises if the architecture is unsupported.
        if is_dll_loaded(pid, os.path.basename(dll_path)):
            return self._running

        logger.info("Injecting into Explorer (PID: %s)", pid)
        h_hook = _inject_via_hook(dll_path, pid)
        if not h_hook:
            logger.error("Injection failed, retrying in 5s")
            self._stop_event.wait(5)
            return False

        with self._state_lock:
            # Injection can finish after destroy() has already run.
            if not self._running:
                UnhookWindowsHookEx(h_hook)
                return False
            self._h_hook = h_hook
        return True

    def _run_pipe_session(self, pipe: int, h_event: int, buffer: ctypes.Array[ctypes.c_char]) -> None:
        """Connect and process messages until the DLL disconnects or shutdown begins."""
        try:
            logger.debug("Waiting for DLL to connect")
            if not self._running or not self._connect_pipe(pipe, h_event) or not self._running:
                return

            logger.debug("DLL Connected")
            with self._state_lock:
                self._unhook()
            self.update_icons.emit()

            while self._running:
                message = self._read_message(pipe, h_event, buffer)
                if message is None or not self._running:
                    break
                self._process_message(message)
        except OSError as e:
            if self._running:
                if e.winerror == ERROR_BROKEN_PIPE:
                    logger.debug("DLL Disconnected")
                elif e.winerror == ERROR_OPERATION_ABORTED:
                    logger.debug("Pipe operation aborted (closing)")
                else:
                    logger.error("Worker error: %s", e)
        except Exception as e:
            if self._running:
                logger.error("Worker error: %s", e)
        finally:
            # A failed connection must release its hook before another injection attempt.
            with self._state_lock:
                self._unhook()
            DisconnectNamedPipe(pipe)

    def _connect_pipe(self, pipe: int, h_event: int) -> bool:
        overlapped = OVERLAPPED(hEvent=h_event)
        ResetEvent(h_event)
        if ConnectNamedPipe(pipe, ctypes.byref(overlapped)):
            return True
        error = GetLastError()
        if error == ERROR_PIPE_CONNECTED:
            return True
        if error != ERROR_IO_PENDING:
            raise ctypes.WinError(error)
        if not self._wait_for_io(pipe, overlapped):
            return False
        success, _ = GetOverlappedResult(pipe, ctypes.byref(overlapped), False)
        if not success:
            raise ctypes.WinError(GetLastError())
        return True

    def _read_message(self, pipe: int, h_event: int, buffer: ctypes.Array[ctypes.c_char]) -> bytes | None:
        chunks: list[bytes] = []
        while self._running:
            overlapped = OVERLAPPED(hEvent=h_event)
            ResetEvent(h_event)
            success = ReadFileOverlapped(pipe, buffer, ctypes.byref(overlapped))
            error = ERROR_SUCCESS if success else GetLastError()
            if error == ERROR_IO_PENDING:
                if not self._wait_for_io(pipe, overlapped):
                    return None
            elif error not in (ERROR_SUCCESS, ERROR_MORE_DATA):
                raise ctypes.WinError(error)

            success, n_read = GetOverlappedResult(pipe, ctypes.byref(overlapped), False)
            error = ERROR_SUCCESS if success else GetLastError()
            if error not in (ERROR_SUCCESS, ERROR_MORE_DATA):
                raise ctypes.WinError(error)
            chunks.append(buffer.raw[:n_read])
            if error == ERROR_SUCCESS:
                return b"".join(chunks)
        return None

    def _wait_for_io(self, pipe: int, overlapped: OVERLAPPED) -> bool:
        """Wait for completion, or cancel and drain the operation before returning."""
        completed = False
        try:
            while self._running:
                wait_result = WaitForSingleObject(overlapped.hEvent, 500)
                if wait_result == WAIT_OBJECT_0:
                    completed = True
                    return True
                if wait_result == WAIT_FAILED:
                    raise ctypes.WinError(GetLastError())
            return False
        finally:
            if not completed:
                CancelIoEx(pipe, ctypes.byref(overlapped))
                GetOverlappedResult(pipe, ctypes.byref(overlapped), True)

    def _process_message(self, data_bytes: bytes) -> None:
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
                icon = Image.frombytes("RGBA", (icon_w, icon_h), bytes(rgba_bytes))  # type: ignore

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

    def _unhook(self) -> None:
        """Release the injection hook. The caller must hold _state_lock."""
        if self._h_hook:
            UnhookWindowsHookEx(self._h_hook)
            self._h_hook = 0

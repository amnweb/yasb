import ctypes
import logging
import os
import string
from collections.abc import Callable
from ctypes import wintypes
from typing import Any, ClassVar, TypedDict, cast, override

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from core.utils.feed import Feed
from core.utils.qml import qml_property
from core.utils.win32.bindings.kernel32 import GetLastError, kernel32
from core.utils.win32.bindings.shell32 import shell32
from core.utils.win32.constants import (
    DRIVE_FIXED,
    FILE_NOTIFY_CHANGE_DIR_NAME,
    FILE_NOTIFY_CHANGE_FILE_NAME,
    INFINITE,
    INVALID_HANDLE_VALUE,
    S_OK,
    SHERB_NOSOUND,
    WAIT_OBJECT_0,
    KnownCLSID,
)
from core.utils.win32.structs import SHQUERYRBINFO
from core.utils.worker import run_in_worker

# The bin is read again at most this often while it keeps changing
COOLDOWN_MS = 500


class BinInfo(TypedDict):
    size_bytes: int
    num_items: int


EMPTY_BIN: BinInfo = {"size_bytes": 0, "num_items": 0}


def _query_bin_info() -> BinInfo:
    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    result = shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
    if result != S_OK:
        raise RuntimeError(f"SHQueryRecycleBinW failed (HRESULT 0x{result & 0xFFFFFFFF:08X})")
    return {"size_bytes": info.i64Size, "num_items": info.i64NumItems}


def _empty_bin() -> None:
    result = shell32.SHEmptyRecycleBinW(None, None, SHERB_NOSOUND)
    if result != S_OK:
        raise RuntimeError(f"SHEmptyRecycleBinW failed (HRESULT 0x{result & 0xFFFFFFFF:08X})")


_emptying = False


def empty_recycle_bin() -> None:
    """Empties the bin after Windows asks to confirm, showing its progress. The watch reads the bin again after."""
    global _emptying
    if _emptying:
        return
    _emptying = True

    def finished(_result: object, error: str) -> None:
        global _emptying
        _emptying = False
        if error:
            logging.error("%s", error)

    run_in_worker(_empty_bin, finished, "Could not empty the Recycle Bin")


def open_recycle_bin() -> None:
    try:
        os.startfile(f"shell:::{{{KnownCLSID.RECYCLE_BIN}}}")
    except OSError as error:
        logging.error("Could not open the Recycle Bin: %s", error)


def _watch_bins(stop: int, notify: Callable[[], None]) -> None:
    """Calls notify once the watches are set, then for each change to a fixed drive's bin, until stop is set."""
    # The stop event goes first, so it wins when a drive is also signaled
    handles = [stop]
    try:
        drives = kernel32.GetLogicalDrives()
        for index, letter in enumerate(string.ascii_uppercase):
            if not drives & (1 << index):
                continue
            if kernel32.WaitForSingleObject(stop, 0) == WAIT_OBJECT_0:
                return
            drive = f"{letter}:\\"
            if kernel32.GetDriveTypeW(drive) != DRIVE_FIXED:
                continue
            change: int = kernel32.FindFirstChangeNotificationW(
                f"{drive}$Recycle.Bin", True, FILE_NOTIFY_CHANGE_DIR_NAME | FILE_NOTIFY_CHANGE_FILE_NAME
            )
            if change != INVALID_HANDLE_VALUE:
                handles.append(change)

        # Read only after all watches are set, so no change goes unseen
        notify()
        wait_handles = (wintypes.HANDLE * len(handles))(*handles)
        while len(handles) > 1:
            result = kernel32.WaitForMultipleObjects(len(handles), wait_handles, False, INFINITE)
            if result == WAIT_OBJECT_0:
                return
            if not WAIT_OBJECT_0 < result < WAIT_OBJECT_0 + len(handles):
                raise RuntimeError(f"Could not wait for Recycle Bin changes: {ctypes.WinError(GetLastError())}")

            notify()
            index = result - WAIT_OBJECT_0
            if not kernel32.FindNextChangeNotification(handles[index]):
                logging.debug("Could not rearm a Recycle Bin watch: %s", ctypes.WinError(GetLastError()))
                kernel32.FindCloseChangeNotification(handles.pop(index))
                wait_handles = (wintypes.HANDLE * len(handles))(*handles)
    finally:
        for change in handles[1:]:
            kernel32.FindCloseChangeNotification(change)


class _Watch:
    """The thread watching the drives' bins and the event that stops it. The event is closed once the thread has
    ended and the watch was released, whichever comes last, so it is never set after being closed."""

    def __init__(self, notify: Callable[[], None]) -> None:
        stop: int | None = kernel32.CreateEventW(None, True, False, None)
        if not stop:
            raise ctypes.WinError(GetLastError())
        self._stop = stop
        self._running = True
        self._released = False
        run_in_worker(lambda: _watch_bins(stop, notify), self._finished, "Could not watch the Recycle Bin")

    def _finished(self, _result: object, error: str) -> None:
        self._running = False
        if error:
            logging.warning("%s", error)
        self._close()

    def release(self) -> None:
        if not self._released:
            self._released = True
            kernel32.SetEvent(self._stop)
            self._close()

    def _close(self) -> None:
        if self._released and not self._running:
            kernel32.CloseHandle(self._stop)


class RecycleBinMonitor(Feed[None]):
    """What the Recycle Bin holds, shared by everything showing it: one watch on the fixed drives' bins while anything
    uses it. The bin is one for all, so the key is None."""

    _feeds: ClassVar[dict[Any, Any]] = {}
    # A drive's bin changed, from the watch thread
    _touched = pyqtSignal()

    def __init__(self, key: None) -> None:
        super().__init__(key)
        self.info: BinInfo = EMPTY_BIN
        # The bin changed since it was last read
        self._stale = False
        # The cooldown: the bin is read again when it ends, if it changed meanwhile
        self._timer.setInterval(COOLDOWN_MS)
        self._touched.connect(self._on_touched)
        touched = self._touched

        def notify() -> None:
            try:
                touched.emit()
            except RuntimeError:
                # The monitor went with its last user while the watch was stopping
                pass

        self._watch: _Watch | None = None
        try:
            self._watch = _Watch(notify)
        except OSError as error:
            logging.warning("Could not watch the Recycle Bin: %s", error)
            self._on_touched()

    @classmethod
    def last_info(cls) -> BinInfo:
        """What the bin held when last read, or nothing while no one watches it."""
        monitor = cls._feeds.get(None)
        return monitor.info if monitor is not None else EMPTY_BIN

    @override
    def _user_destroyed(self) -> None:
        super()._user_destroyed()
        if self._users <= 0 and self._watch is not None:
            self._watch.release()
            self._watch = None

    def _on_touched(self) -> None:
        self._stale = True
        if not self.loading and not self._timer.isActive():
            self.fetch()

    @pyqtSlot()
    def fetch(self) -> None:
        if self.loading or not self._stale:
            return
        self._stale = False
        self.loading = True
        self._timer.start()
        request = self._request

        def read(result: object, error: str) -> None:
            # The monitor is gone once its last user left
            if request == self._request:
                self._read(result, error)

        run_in_worker(_query_bin_info, read, "Could not query the Recycle Bin")

    def _read(self, result: object, error: str) -> None:
        self.loading = False
        if error:
            logging.debug("%s", error)
        elif result != self.info:
            self.info = cast(BinInfo, result)
            self.changed.emit()
        if not self._timer.isActive():
            self.fetch()


class RecycleBin(QObject):
    """The Recycle Bin's contents and actions for a QML widget."""

    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor = RecycleBinMonitor.join(None, self)
        self._monitor.changed.connect(self.changed)

    @qml_property("qulonglong", notify=changed)
    def itemCount(self) -> int:
        return self._monitor.info["num_items"]

    @qml_property("qulonglong", notify=changed)
    def sizeBytes(self) -> int:
        return self._monitor.info["size_bytes"]

    @pyqtSlot()
    def open(self) -> None:
        # Explorer can change focus and close the widget's menu during the launch
        QTimer.singleShot(0, open_recycle_bin)

    @pyqtSlot()
    def empty(self) -> None:
        empty_recycle_bin()

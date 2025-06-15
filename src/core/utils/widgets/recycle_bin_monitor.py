import ctypes
import logging
import os
import string
import threading
import time
from ctypes import wintypes

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from settings import DEBUG

# Windows API constants
FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
WAIT_OBJECT_0 = 0
INFINITE = 0xFFFFFFFF


class RecycleBinMonitor(QObject):
    """Utility class to monitor Recycle Bin status and changes"""

    # Signal that will be emitted when recycle bin status changes
    bin_updated = pyqtSignal(dict)

    # Add these class variables
    _instance = None
    _is_monitoring = False

    @classmethod
    def get_instance(cls):
        """Singleton pattern to ensure only one monitor is running"""
        if cls._instance is None:
            cls._instance = RecycleBinMonitor()

        # Auto-start monitoring when instance is requested
        if not cls._instance._is_monitoring:
            cls._instance.start_monitoring()

        return cls._instance

    def __init__(self):
        super().__init__()
        self._active = False
        self._monitoring_thread = None
        self._last_info = {"size_bytes": 0, "num_items": 0}
        self._last_emit_time = 0  # Track the last time we emitted a signal
        self._throttle_interval = 0.2  # 100ms in seconds
        self._pending_update = None  # Store pending update
        self._lock = threading.Lock()  # Lock for thread safety

    def start_monitoring(self):
        """Start monitoring the recycle bin for changes"""
        if self._is_monitoring:
            return  # Prevent multiple starts

        self._active = True
        self._monitoring_thread = threading.Thread(target=self._monitor_recycle_bin, daemon=True)
        self._monitoring_thread.start()

        # Get initial info
        info = self.get_recycle_bin_info()
        if info:
            self._last_info = info
            self.bin_updated.emit(info)

        self._is_monitoring = True

    def stop_monitoring(self):
        """Stop monitoring the recycle bin"""
        self._active = False
        if hasattr(self, "_stop_event"):
            kernel32 = ctypes.windll.kernel32
            kernel32.SetEvent(self._stop_event)  # Signal the stop event

        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=1.0)  # Wait up to 1 second

        # Clean up stop event handle
        if hasattr(self, "_stop_event"):
            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle(self._stop_event)
            del self._stop_event

    def get_recycle_bin_info(self):
        """Get information about the Recycle Bin using SHQueryRecycleBinW"""

        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]

        shell32 = ctypes.windll.shell32

        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)

        # Query all Recycle Bins (pszRootPath = None)
        result = shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

        if result == 0:  # S_OK
            return {"size_bytes": info.i64Size, "num_items": info.i64NumItems}
        else:
            return {"size_bytes": 0, "num_items": 0}

    def empty_recycle_bin(self):
        """Empty the recycle bin with no confirmation, progress UI, or sound"""
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004

        # Get current bin info to check if it's already empty
        current_info = self.get_recycle_bin_info()
        if current_info["num_items"] == 0:
            if DEBUG:
                logging.info("Recycle bin is already empty")
            return True

        try:
            shell32 = ctypes.windll.shell32
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            result = shell32.SHEmptyRecycleBinW(None, None, flags)

            if result == 0:  # S_OK
                if DEBUG:
                    logging.info("Recycle bin emptied successfully")
                # Force an update
                info = self.get_recycle_bin_info()
                if info:
                    self._last_info = info
                    self.bin_updated.emit(info)
                return True
            else:
                error = ctypes.WinError(result)
                logging.error(f"Failed to empty recycle bin: {error}")
                return False
        except Exception as e:
            logging.error(f"Error emptying recycle bin: {e}")
            return False

    def empty_recycle_bin_async(self):
        """Empty the recycle bin asynchronously

        Returns:
            tuple: (signal, thread) - The finished signal and the thread object
        """
        thread = EmptyBinThread(self)
        thread.finished.connect(thread.deleteLater)  # Auto-cleanup thread when done
        thread.start()
        # Return both the signal and the thread so the caller can keep a reference
        return thread.finished, thread

    def _cleanup_empty_thread(self):
        """Clean up the empty thread resources"""
        if hasattr(self, "_empty_thread") and self._empty_thread:
            self._empty_thread.deleteLater()
            self._empty_thread = None

    def open_recycle_bin(self):
        """Open the recycle bin in Explorer"""
        try:
            shell32 = ctypes.windll.shell32
            result = shell32.ShellExecuteW(None, "open", "shell:RecycleBinFolder", None, None, 1)

            if result <= 32:  # Error codes are <= 32
                logging.error(f"Failed to open recycle bin: {result}")
                return False
            return True
        except Exception as e:
            logging.error(f"Error opening recycle bin: {e}")
            return False

    def _emit_update(self, bin_info):
        """
        Emit an update with throttling because the Recycle Bin can change rapidly with multiple files being added or removed.
        This method ensures that we only emit updates at a specified interval to avoid flooding the signal.
        """
        with self._lock:
            current_time = time.time()
            time_since_last = current_time - self._last_emit_time

            # Always store the latest info
            self._pending_update = bin_info

            # If it's been long enough since our last emit, send immediately
            if time_since_last >= self._throttle_interval:
                self._last_info = bin_info
                self._last_emit_time = current_time
                self.bin_updated.emit(bin_info)
                self._pending_update = None
            else:
                # Otherwise schedule a delayed emission if not already scheduled
                if not hasattr(self, "_timer_active") or not self._timer_active:
                    self._timer_active = True
                    delay = self._throttle_interval - time_since_last
                    threading.Timer(delay, self._emit_pending_update).start()

    def _emit_pending_update(self):
        """Emit the pending update after the throttle interval"""
        with self._lock:
            if self._pending_update:
                self._last_info = self._pending_update
                self._last_emit_time = time.time()
                self.bin_updated.emit(self._pending_update)
                self._pending_update = None
            self._timer_active = False

    def _monitor_recycle_bin(self):
        """Monitor the Recycle Bin status using Windows change notifications"""
        kernel32 = ctypes.windll.kernel32

        # Create an event handle that will be used to signal thread termination
        self._stop_event = kernel32.CreateEventW(None, True, False, None)

        def get_all_drives():
            drive_bitmask = kernel32.GetLogicalDrives()
            drives = []
            for i in range(26):
                if drive_bitmask & (1 << i):
                    drives.append(string.ascii_uppercase[i] + ":\\")
            return drives

        def monitor_drive_recycle_bin(drive_path):
            recycle_bin_path = os.path.join(drive_path, "$Recycle.Bin")
            if not os.path.exists(recycle_bin_path):
                return

            # Create a directory handle
            dir_handle = kernel32.CreateFileW(
                recycle_bin_path,
                0x0001,  # FILE_LIST_DIRECTORY
                0x0007,  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
                None,
                0x0003,  # OPEN_EXISTING
                0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS (required for directories)
                None,
            )

            if dir_handle == -1:
                logging.error(f"Failed to open directory handle for {recycle_bin_path}: {ctypes.WinError()}")
                return

            try:
                # Create a notification event
                change_handle = kernel32.FindFirstChangeNotificationW(
                    recycle_bin_path,
                    True,  # Watch subdirectories
                    FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_DIR_NAME | FILE_NOTIFY_CHANGE_SIZE,
                )

                if change_handle == -1:
                    logging.error(f"Failed to set up change notification for {recycle_bin_path}: {ctypes.WinError()}")
                    return

                try:
                    wait_handles = (wintypes.HANDLE * 2)(change_handle, self._stop_event)
                    if DEBUG:
                        logging.debug(f"Monitoring {recycle_bin_path} for changes...")
                    while self._active:
                        # Wait for either a change notification or the stop event
                        # Using INFINITE for true event-based notification with no timer
                        result = kernel32.WaitForMultipleObjects(
                            2,  # Number of handles
                            wait_handles,  # Array of handles
                            False,  # WaitAll=False, so return when any handle is signaled
                            INFINITE,  # Wait indefinitely, no timeout
                        )

                        if not self._active or result == WAIT_OBJECT_0 + 1:  # Stop event was signaled
                            break

                        if result == WAIT_OBJECT_0:  # Change notification was signaled
                            # Change detected, get updated info
                            bin_info = self.get_recycle_bin_info()
                            if bin_info:
                                # Only emit signal if the info has changed
                                if (
                                    bin_info["size_bytes"] != self._last_info["size_bytes"]
                                    or bin_info["num_items"] != self._last_info["num_items"]
                                ):
                                    # Use the throttled emission instead of direct emit
                                    self._emit_update(bin_info)

                            # Reset the notification for the next change
                            if not kernel32.FindNextChangeNotification(change_handle):
                                logging.error(
                                    f"Failed to reset change notification for {recycle_bin_path}: {ctypes.WinError()}"
                                )
                                break
                        else:
                            # Error occurred
                            logging.error(f"Error waiting for change notification: {ctypes.WinError()}")
                            break
                finally:
                    # Clean up notification handle
                    if change_handle != -1:
                        kernel32.FindCloseChangeNotification(change_handle)
            finally:
                # Clean up directory handle
                if dir_handle != -1:
                    kernel32.CloseHandle(dir_handle)

        # Monitor all drive recycle bins in parallel
        monitor_threads = []
        for drive in get_all_drives():
            thread = threading.Thread(target=monitor_drive_recycle_bin, args=(drive,), daemon=True)
            thread.start()
            monitor_threads.append(thread)


class EmptyBinThread(QThread):
    finished = pyqtSignal()

    def __init__(self, monitor):
        super().__init__()
        self.monitor = monitor

    def run(self):
        self.monitor.empty_recycle_bin()
        self.finished.emit()

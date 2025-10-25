import ctypes
import logging
import os
import string
import threading
import time
from ctypes import wintypes

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.utils.win32.bindings import kernel32, shell32
from core.utils.win32.constants import (
    FILE_FLAG_BACKUP_SEMANTICS,
    FILE_LIST_DIRECTORY,
    FILE_NOTIFY_CHANGE_DIR_NAME,
    FILE_NOTIFY_CHANGE_FILE_NAME,
    FILE_SHARE_DELETE,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    INFINITE,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    S_OK,
    SHERB_NOCONFIRMATION,
    SHERB_NOPROGRESSUI,
    SHERB_NOSOUND,
    WAIT_FAILED,
    WAIT_OBJECT_0,
    KnownCLSID,
)
from core.utils.win32.structs import SHQUERYRBINFO
from settings import DEBUG


class BinInfoWorker(QThread):
    """Reusable worker thread to query recycle bin info on demand"""

    info_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._request_event = threading.Event()
        self._stop_event = threading.Event()

    def run(self):
        """Wait for requests and query bin info"""
        while True:
            self._request_event.wait()
            self._request_event.clear()

            if self._stop_event.is_set():
                break

            info = self._get_recycle_bin_info()
            self.info_ready.emit(info)

    def request_query(self):
        """Request a bin info query"""
        self._request_event.set()

    def stop(self):
        """Stop the worker thread"""
        self._stop_event.set()
        self._request_event.set()
        self.wait(1000)

    def _get_recycle_bin_info(self):
        """Get information about the Recycle Bin using SHQueryRecycleBinW"""
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)

        # Query all Recycle Bins (pszRootPath = None)
        result = shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

        if result == S_OK:
            return {"size_bytes": info.i64Size, "num_items": info.i64NumItems}

        if DEBUG:
            error_code = result & 0xFFFF  # Equivalent to HRESULT_CODE macro
            try:
                error_message = str(ctypes.WinError(error_code))
            except Exception:
                error_message = f"HRESULT 0x{result & 0xFFFFFFFF:08X}"
            logging.error("SHQueryRecycleBinW failed: %s", error_message)

        return {"size_bytes": 0, "num_items": 0}


class EmptyBinThread(QThread):
    def __init__(self, monitor, show_confirmation=False, show_progress=False, play_sound=False):
        super().__init__()
        self.monitor = monitor
        self.show_confirmation = show_confirmation
        self.show_progress = show_progress
        self.play_sound = play_sound

    def run(self):
        self.monitor.empty_recycle_bin(self.show_confirmation, self.show_progress, self.play_sound)


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
        return cls._instance

    def __init__(self):
        super().__init__()
        self._active = False
        self._monitoring_thread = None
        self._watchers = []  # Win32DirectoryWatcher instances
        self._last_info = {"size_bytes": 0, "num_items": 0}
        self._lock = threading.Lock()
        self._query_worker = None  # Reusable worker thread for async queries
        self._query_pending = False  # Flag to prevent multiple simultaneous queries
        self._poll_timer = None  # Timer for periodic polling during bursts
        self._poll_interval = 1  # Poll interval in seconds during bursts
        self._last_change_time = time.monotonic()  # Timestamp of last detected change
        self._last_poll_time = 0.0  # Timestamp of last direct poll trigger
        self._subscribers = set()  # Track subscribers (widget instances)

    def subscribe(self, subscriber_id):
        """Subscribe to recycle bin updates. Starts monitoring if this is the first subscriber.

        Args:
            subscriber_id: Unique identifier for the subscriber (e.g., id(widget_instance))

        Returns:
            bool: True if subscription successful
        """
        with self._lock:
            self._subscribers.add(subscriber_id)
            subscriber_count = len(self._subscribers)

        # Start monitoring if this is the first subscriber
        if subscriber_count == 1 and not self._is_monitoring:
            if DEBUG:
                logging.debug(f"RecycleBinMonitor first subscriber {subscriber_id}, starting monitoring")
            self.start_monitoring()
        else:
            if DEBUG:
                logging.debug(f"RecycleBinMonitor subscriber {subscriber_id} added (total: {subscriber_count})")

        return True

    def unsubscribe(self, subscriber_id):
        """Unsubscribe from recycle bin updates. Stops monitoring if this is the last subscriber.

        Args:
            subscriber_id: Unique identifier for the subscriber
        """
        with self._lock:
            self._subscribers.discard(subscriber_id)
            subscriber_count = len(self._subscribers)

        # Stop monitoring if no more subscribers
        if subscriber_count == 0 and self._is_monitoring:
            if DEBUG:
                logging.debug(f"RecycleBinMonitor last subscriber {subscriber_id} removed (stopping monitoring)")
            self.stop_monitoring()
        else:
            if DEBUG:
                logging.debug(f"RecycleBinMonitor subscriber {subscriber_id} removed (remaining: {subscriber_count})")

    def start_monitoring(self):
        """Start monitoring the recycle bin for changes"""
        if self._is_monitoring:
            return

        self._active = True
        self._last_poll_time = time.monotonic() - self._poll_interval

        # Start the reusable worker thread
        self._query_worker = BinInfoWorker()
        self._query_worker.info_ready.connect(self._on_bin_info_ready)
        self._query_worker.start()

        self._monitoring_thread = threading.Thread(target=self._monitor_recycle_bin, daemon=True)
        self._monitoring_thread.start()

        # Get initial info
        self._query_bin_info_async(mark_poll_time=False)

        self._is_monitoring = True

    def stop_monitoring(self):
        """Stop monitoring the recycle bin"""
        self._active = False
        self._is_monitoring = False

        # Stop polling timer
        self._stop_poll_timer()

        # Stop any active watchers
        for watcher in getattr(self, "_watchers", []):
            try:
                watcher.stop(timeout=1.0)
            except Exception:
                logging.exception("Error stopping watcher")
        self._watchers = []

        # If there was a legacy monitoring thread, join it
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=1.0)

        # Stop the worker thread
        if self._query_worker:
            self._query_worker.stop()
            self._query_worker.deleteLater()
            self._query_worker = None

    def empty_recycle_bin(self, show_confirmation=False, show_progress=False, play_sound=False):
        """Empty the recycle bin with configurable UI options

        Args:
            show_confirmation: If True, show confirmation dialog before emptying
            show_progress: If True, show progress dialog while emptying
            play_sound: If True, play sound when operation completes
        """

        # Check if already empty using cached info (fast, no blocking)
        if self._last_info["num_items"] == 0:
            return True

        try:
            # Build flags based on parameters
            flags = 0
            if not show_confirmation:
                flags |= SHERB_NOCONFIRMATION
            if not show_progress:
                flags |= SHERB_NOPROGRESSUI
            if not play_sound:
                flags |= SHERB_NOSOUND

            result = shell32.SHEmptyRecycleBinW(None, None, flags)
            # We can't reliably detect cancellation, so we just check for success/error
            if result == S_OK:
                return True

            error_code = result & 0xFFFF
            try:
                error_message = str(ctypes.WinError(error_code))
            except Exception:
                error_message = f"HRESULT 0x{result & 0xFFFFFFFF:08X}"
            logging.error("Failed to empty recycle bin: %s", error_message)
            return False
        except Exception as e:
            logging.error(f"Error emptying recycle bin: {e}")
            return False

    def empty_recycle_bin_async(self, show_confirmation=False, show_progress=False, play_sound=False):
        """Empty the recycle bin asynchronously with configurable UI options

        Args:
            show_confirmation: If True, show confirmation dialog before emptying
            show_progress: If True, show progress dialog while emptying
            play_sound: If True, play sound when operation completes

        Returns:
            tuple: (signal, thread) - The finished signal and the thread object
        """
        thread = EmptyBinThread(self, show_confirmation, show_progress, play_sound)
        thread.finished.connect(thread.deleteLater)  # Auto-cleanup thread when done
        thread.start()
        # Return both the signal and the thread so the caller can keep a reference
        return thread.finished, thread

    def open_recycle_bin(self):
        """Open the recycle bin in Explorer"""
        try:
            os.startfile(f"shell:::{{{KnownCLSID.RECYCLE_BIN}}}")
        except Exception as e:
            logging.error(f"Error opening recycle bin: {e}")
            return False

    def _query_bin_info_async(self, mark_poll_time=True):
        """Request bin info query from the worker thread

        Args:
            mark_poll_time: When True, record the trigger time to throttle bursts.
        """
        with self._lock:
            if self._query_pending or not self._query_worker:
                return
            self._query_pending = True
            if mark_poll_time:
                self._last_poll_time = time.monotonic()

        self._query_worker.request_query()

    def _on_bin_info_ready(self, bin_info):
        """Handle bin info result from async query and emit if changed"""
        if not bin_info:
            with self._lock:
                self._query_pending = False
            return

        with self._lock:
            self._query_pending = False

            # Only emit signal if the info has changed
            if (
                bin_info["size_bytes"] != self._last_info["size_bytes"]
                or bin_info["num_items"] != self._last_info["num_items"]
            ):
                self._last_info = bin_info
                should_emit = True
            else:
                # Update last_info even if unchanged (for initial load)
                if self._last_info["size_bytes"] == 0 and self._last_info["num_items"] == 0:
                    self._last_info = bin_info
                    should_emit = True
                else:
                    should_emit = False

        if should_emit:
            self.bin_updated.emit(bin_info)

    def _start_poll_timer(self):
        """Start polling timer for burst handling"""
        with self._lock:
            if self._poll_timer or not self._active:
                return

            timer = threading.Timer(self._poll_interval, self._poll_tick)
            timer.daemon = True
            self._poll_timer = timer
            timer.start()

    def _stop_poll_timer(self):
        """Stop the polling timer"""
        with self._lock:
            if self._poll_timer:
                self._poll_timer.cancel()
                self._poll_timer = None

    def _poll_tick(self):
        """Periodic polling callback during bursts"""
        with self._lock:
            self._poll_timer = None

            if not self._active:
                return

            # Check if we should continue polling
            time_since_change = time.monotonic() - self._last_change_time
            should_continue = time_since_change < self._poll_interval

        # Query current state
        self._query_bin_info_async()

        # Reschedule if activity is ongoing
        if should_continue:
            self._start_poll_timer()

    def _handle_change_notification(self):
        """Handle filesystem change notification"""
        with self._lock:
            now = time.monotonic()
            self._last_change_time = now
            has_timer = self._poll_timer is not None
            query_pending = self._query_pending
            should_query_now = not query_pending and (now - self._last_poll_time) >= self._poll_interval

        # Start polling if not already running
        if should_query_now:
            self._query_bin_info_async()

        if not has_timer:
            self._start_poll_timer()

    def get_all_drives(self):
        drive_bitmask = kernel32.GetLogicalDrives()
        drives = []
        for i in range(26):
            if drive_bitmask & (1 << i):
                drives.append(string.ascii_uppercase[i] + ":\\")
        return drives

    def _monitor_recycle_bin(self):
        """Monitor the Recycle Bin status using Windows change notifications"""

        # Create watchers for each drive's Recycle Bin folder
        for drive in self.get_all_drives():
            recycle_bin_path = os.path.join(drive, "$Recycle.Bin")
            if not os.path.exists(recycle_bin_path):
                continue

            watcher = Win32DirectoryWatcher(recycle_bin_path, callback=self._handle_change_notification)
            if watcher.start():
                self._watchers.append(watcher)


class Win32DirectoryWatcher:
    """Small helper that watches a directory for changes using Win32 APIs"""

    def __init__(self, path, callback):
        self.path = path
        self.callback = callback
        self.watch_subtree = True
        self.flag = FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_DIR_NAME

        self._change_handle = INVALID_HANDLE_VALUE
        self._dir_handle = INVALID_HANDLE_VALUE
        self._stop_event = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return True

        # Create stop event
        self._stop_event = kernel32.CreateEventW(None, True, False, None)
        if not self._stop_event:
            logging.error(f"Watcher: failed to create stop event for {self.path}: {ctypes.WinError()}")
            self._stop_event = None
            return False

        # Open directory handle (required on some Windows versions)
        self._dir_handle = kernel32.CreateFileW(
            self.path,
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )

        if self._dir_handle == INVALID_HANDLE_VALUE:
            logging.error(f"Watcher: failed to open dir handle for {self.path}: {ctypes.WinError()}")
            if self._stop_event is not None:
                kernel32.CloseHandle(self._stop_event)
                self._stop_event = None
            return False

        # Register change notification
        self._change_handle = kernel32.FindFirstChangeNotificationW(self.path, self.watch_subtree, self.flag)
        if self._change_handle == INVALID_HANDLE_VALUE:
            logging.error(f"Watcher: failed to register change notification for {self.path}: {ctypes.WinError()}")
            if self._dir_handle != INVALID_HANDLE_VALUE:
                kernel32.CloseHandle(self._dir_handle)
                self._dir_handle = INVALID_HANDLE_VALUE
            if self._stop_event is not None:
                kernel32.CloseHandle(self._stop_event)
                self._stop_event = None
            return False

        # Start thread
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self):
        wait_handles = (wintypes.HANDLE * 2)(self._change_handle, self._stop_event)
        while self._running:
            result = kernel32.WaitForMultipleObjects(2, wait_handles, False, INFINITE)
            if not self._running:
                break

            if result == WAIT_FAILED:
                logging.error(f"Watcher: wait failed for {self.path}: {ctypes.WinError()}")
                break

            if result == WAIT_OBJECT_0:
                try:
                    self.callback()
                except Exception:
                    logging.exception("Watcher callback raised")

                # Reset change notification
                if not kernel32.FindNextChangeNotification(self._change_handle):
                    logging.error(f"Watcher: failed to reset notification for {self.path}: {ctypes.WinError()}")
                    break
            elif result == WAIT_OBJECT_0 + 1:
                # Stop event signaled
                break
            else:
                logging.error(f"Watcher: unexpected wait result: {result}")
                break

        # Cleanup
        if self._change_handle != INVALID_HANDLE_VALUE:
            kernel32.FindCloseChangeNotification(self._change_handle)
            self._change_handle = INVALID_HANDLE_VALUE
        if self._dir_handle != INVALID_HANDLE_VALUE:
            kernel32.CloseHandle(self._dir_handle)
            self._dir_handle = INVALID_HANDLE_VALUE
        if self._stop_event is not None:
            kernel32.CloseHandle(self._stop_event)
            self._stop_event = None

    def stop(self, timeout=None):
        if not self._running:
            return
        self._running = False
        if self._stop_event is not None:
            kernel32.SetEvent(self._stop_event)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

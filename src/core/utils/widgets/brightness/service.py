"""
Brightness service using Windows API.
Provides DDC/CI support for external monitors and LCD support for laptops.
"""

import logging
import threading
import time
from ctypes import byref, c_ulong, sizeof
from ctypes.wintypes import BYTE, DWORD, HANDLE
from typing import ClassVar

from PyQt6.QtCore import QObject, pyqtSignal

from core.utils.win32.bindings.dxva2 import PHYSICAL_MONITOR, VCP_BRIGHTNESS, dxva2
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.user32 import MONITORENUMPROC, user32
from core.utils.win32.constants import (
    DISPLAY_BRIGHTNESS_POLICY_BOTH,
    INVALID_HANDLE_VALUE,
    IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS,
    IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS,
)
from core.utils.win32.structs import DISPLAY_BRIGHTNESS
from settings import DEBUG


class _MonitorInfo:
    """Internal monitor state tracking."""

    __slots__ = ("hmonitor", "supports_ddc", "supports_lcd", "brightness", "tested", "reported")

    def __init__(self, hmonitor: int) -> None:
        self.hmonitor = hmonitor
        self.supports_ddc = False
        self.supports_lcd = False
        self.brightness: int | None = None
        self.tested = False
        self.reported = False


class BrightnessService(QObject):
    """
    Singleton service for monitor brightness control.
    """

    # Singleton instance
    _instance: ClassVar[BrightnessService | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    # Signal emitted when brightness changes (hmonitor, brightness_or_none)
    brightness_changed = pyqtSignal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self._monitors: dict[int, _MonitorInfo] = {}
        self._lcd_handle: HANDLE | None = None
        self._lcd_tested = False
        self._lcd_available = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending_set: dict[int, tuple[int, float]] = {}

        # Configuration
        self._poll_interval = 5.0  # seconds between polls
        self._set_debounce = 0.05  # seconds to wait before applying set

    @classmethod
    def instance(cls) -> BrightnessService:
        """Get the singleton instance, creating it if needed."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._start()
        return cls._instance

    @classmethod
    def cleanup(cls) -> None:
        """Stop and cleanup the singleton instance."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance._stop()
                cls._instance = None

    # Public API
    def get_brightness(self, hmonitor: int) -> int | None:
        """Get cached brightness for a monitor."""
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            return monitor.brightness if monitor else None

    def set_brightness(self, hmonitor: int, value: int) -> None:
        """Queue a brightness change."""
        value = max(0, min(100, value))
        with self._lock:
            self._pending_set[hmonitor] = (value, time.monotonic())
            # Update cache immediately for responsive UI
            if hmonitor in self._monitors:
                self._monitors[hmonitor].brightness = value

    # Internal methods
    def _start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="BrightnessService")
        self._thread.start()

    def _stop(self) -> None:
        """Stop the background thread and cleanup resources."""
        self._running = False
        if self._lcd_handle:
            kernel32.CloseHandle(self._lcd_handle)
            self._lcd_handle = None

    def _run(self) -> None:
        """Background thread main loop."""
        self._enumerate_monitors()
        if DEBUG:
            logging.info(f"BrightnessService started with {len(self._monitors)} monitors")

        # Initial poll
        self._poll_all_monitors()
        last_poll = time.monotonic()

        while self._running:
            now = time.monotonic()

            # Process pending brightness changes
            self._process_pending_sets(now)

            # Periodic polling
            if now - last_poll >= self._poll_interval:
                last_poll = now
                self._poll_all_monitors()

            time.sleep(0.05)

    def _process_pending_sets(self, now: float) -> None:
        """Process debounced set operations."""
        with self._lock:
            pending = list(self._pending_set.items())

        for hmonitor, (value, timestamp) in pending:
            if now - timestamp < self._set_debounce:
                continue

            with self._lock:
                # Verify this is still the latest pending value
                current = self._pending_set.get(hmonitor)
                if current is None or current[1] != timestamp:
                    continue
                del self._pending_set[hmonitor]

            self._apply_brightness(hmonitor, value)

    def _poll_all_monitors(self) -> None:
        """Poll brightness for supported monitors only and emit changes."""
        with self._lock:
            # Only poll monitors that support brightness (DDC or LCD)
            # Skip monitors that have been tested and don't support either
            hmonitors = [
                hmon
                for hmon, info in self._monitors.items()
                if not info.tested or info.supports_ddc or info.supports_lcd
            ]

        for hmonitor in hmonitors:
            brightness = self._read_brightness(hmonitor)

            with self._lock:
                monitor = self._monitors.get(hmonitor)
                if not monitor:
                    continue
                old_brightness = monitor.brightness
                was_reported = monitor.reported
                monitor.brightness = brightness
                monitor.reported = True

            # Emit on first report or change
            if not was_reported or old_brightness != brightness:
                self.brightness_changed.emit(hmonitor, brightness)

    def _enumerate_monitors(self) -> None:
        """Enumerate all system monitors."""
        with self._lock:
            self._monitors.clear()

        def enum_callback(hmonitor, hdc, rect, lparam):
            hmon = int(hmonitor)
            with self._lock:
                self._monitors[hmon] = _MonitorInfo(hmon)
            if DEBUG:
                logging.info(f"BrightnessService found monitor: {hmon}")
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(enum_callback), 0)

    # Brightness read/write operations
    def _read_brightness(self, hmonitor: int) -> int | None:
        """Read current brightness for a monitor."""
        with self._lock:
            if hmonitor not in self._monitors:
                self._monitors[hmonitor] = _MonitorInfo(hmonitor)
            monitor = self._monitors[hmonitor]

        # Test capabilities on first access
        if not monitor.tested:
            monitor.supports_ddc = self._test_ddc(hmonitor)
            monitor.supports_lcd = self._test_lcd()
            monitor.tested = True
            if DEBUG:
                logging.info(f"Monitor {hmonitor}: DDC={monitor.supports_ddc}, LCD={monitor.supports_lcd}")

        # Try DDC first (external monitors), then LCD (laptops)
        if monitor.supports_ddc:
            brightness = self._read_ddc(hmonitor)
            if brightness is not None:
                return brightness

        if monitor.supports_lcd:
            return self._read_lcd()

        return None

    def _apply_brightness(self, hmonitor: int, value: int) -> bool:
        """Apply brightness to a monitor."""
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            if not monitor:
                return False

        if monitor.supports_ddc and self._write_ddc(hmonitor, value):
            return True

        if monitor.supports_lcd and self._write_lcd(value):
            return True

        return False

    # DDC/CI operations
    def _test_ddc(self, hmonitor: int) -> bool:
        """Test if monitor supports DDC/CI brightness control."""
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return False

            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return False

            handle = monitors[0].hPhysicalMonitor
            actual_handle = handle if handle is not None else 0

            try:
                current, maximum = DWORD(), DWORD()
                for _ in range(3):
                    if dxva2.GetVCPFeatureAndVCPFeatureReply(
                        actual_handle, BYTE(VCP_BRIGHTNESS), None, byref(current), byref(maximum)
                    ):
                        return True
                return False
            finally:
                if handle is not None:
                    dxva2.DestroyPhysicalMonitor(handle)
        except Exception:
            return False

    def _read_ddc(self, hmonitor: int) -> int | None:
        """Read brightness via DDC/CI."""
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return None

            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return None

            handle = monitors[0].hPhysicalMonitor
            actual_handle = handle if handle is not None else 0

            try:
                current, maximum = DWORD(), DWORD()
                for _ in range(3):
                    if dxva2.GetVCPFeatureAndVCPFeatureReply(
                        actual_handle, BYTE(VCP_BRIGHTNESS), None, byref(current), byref(maximum)
                    ):
                        return int((current.value / max(maximum.value, 1)) * 100)
                return None
            finally:
                if handle is not None:
                    dxva2.DestroyPhysicalMonitor(handle)
        except Exception:
            return None

    def _write_ddc(self, hmonitor: int, value: int) -> bool:
        """Write brightness via DDC/CI."""
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return False

            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return False

            handle = monitors[0].hPhysicalMonitor
            actual_handle = handle if handle is not None else 0

            try:
                for _ in range(3):
                    if dxva2.SetVCPFeature(actual_handle, BYTE(VCP_BRIGHTNESS), DWORD(value)):
                        return True
                return False
            finally:
                if handle is not None:
                    dxva2.DestroyPhysicalMonitor(handle)
        except Exception:
            return False

    # LCD operations
    def _test_lcd(self) -> bool:
        """Test if LCD brightness control is available."""
        if self._lcd_tested:
            return self._lcd_available

        self._lcd_tested = True
        try:
            handle = kernel32.CreateFileW("\\\\.\\LCD", 0xC0000000, 0x03, None, 3, 0, None)
            if handle and handle != INVALID_HANDLE_VALUE:
                self._lcd_handle = handle
                self._lcd_available = True
                return True
        except Exception:
            pass
        return False

    def _read_lcd(self) -> int | None:
        """Read brightness via LCD device."""
        if not self._lcd_handle:
            return None
        try:
            brightness = DISPLAY_BRIGHTNESS()
            bytes_returned = c_ulong()
            if kernel32.DeviceIoControl(
                self._lcd_handle,
                IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS,
                None,
                0,
                byref(brightness),
                sizeof(brightness),
                byref(bytes_returned),
                None,
            ):
                return brightness.ucACBrightness
        except Exception:
            pass
        return None

    def _write_lcd(self, value: int) -> bool:
        """Write brightness via LCD device."""
        if not self._lcd_handle:
            return False
        try:
            brightness = DISPLAY_BRIGHTNESS()
            brightness.ucDisplayPolicy = DISPLAY_BRIGHTNESS_POLICY_BOTH
            brightness.ucACBrightness = value
            brightness.ucDCBrightness = value
            bytes_returned = c_ulong()
            return bool(
                kernel32.DeviceIoControl(
                    self._lcd_handle,
                    IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS,
                    byref(brightness),
                    sizeof(brightness),
                    None,
                    0,
                    byref(bytes_returned),
                    None,
                )
            )
        except Exception:
            return False

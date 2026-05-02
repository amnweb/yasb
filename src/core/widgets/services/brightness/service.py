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

from core.utils.win32.bindings.dxva2 import PHYSICAL_MONITOR, VCP_BRIGHTNESS, VCP_CONTRAST, dxva2
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.user32 import MONITORENUMPROC, user32
from core.utils.win32.constants import (
    DISPLAY_BRIGHTNESS_POLICY_BOTH,
    INVALID_HANDLE_VALUE,
    IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS,
    IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS,
)
from core.utils.win32.structs import DISPLAY_BRIGHTNESS
from core.utils.win32.utils import get_monitor_info
from core.widgets.services.brightness.display_targets import get_active_display_targets


class _MonitorInfo:
    """Internal monitor state tracking."""

    __slots__ = (
        "hmonitor",
        "supports_ddc",
        "supports_lcd",
        "brightness",
        "tested",
        "reported",
        "name",
        "connection_type",
        "contrast",
        "supports_contrast",
        "contrast_tested",
    )

    def __init__(self, hmonitor: int) -> None:
        self.hmonitor = hmonitor
        self.supports_ddc = False
        self.supports_lcd = False
        self.brightness: int | None = None
        self.tested = False
        self.reported = False
        self.name: str = ""
        self.connection_type: str = ""
        self.contrast: int | None = None
        self.supports_contrast: bool = False
        self.contrast_tested: bool = False


class BrightnessService(QObject):
    """
    Singleton service for monitor brightness control.
    """

    # Singleton instance
    _instance: ClassVar[BrightnessService | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    # Signals emitted when values change (hmonitor, value_or_none)
    brightness_changed = pyqtSignal(int, object)
    contrast_changed = pyqtSignal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self._monitors: dict[int, _MonitorInfo] = {}
        self._lcd_handle: HANDLE | None = None
        self._lcd_tested = False
        self._lcd_available = False
        self._lcd_owner: int | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending_set: dict[int, tuple[int, float]] = {}
        self._pending_contrast_set: dict[int, tuple[int, float]] = {}

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

    def get_contrast(self, hmonitor: int) -> int | None:
        """Get cached contrast for a monitor."""
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            return monitor.contrast if monitor else None

    def set_contrast(self, hmonitor: int, value: int) -> None:
        """Queue a contrast change."""
        value = max(0, min(100, value))
        with self._lock:
            self._pending_contrast_set[hmonitor] = (value, time.monotonic())
            if hmonitor in self._monitors:
                self._monitors[hmonitor].contrast = value

    def supports_contrast(self, hmonitor: int) -> bool:
        """Return True if the monitor supports DDC contrast control."""
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            return monitor.supports_contrast if monitor else False

    def get_monitors(self) -> list[tuple[int, str]]:
        """Return list of (hmonitor, name) for all known monitors."""
        with self._lock:
            return [(hmon, info.name) for hmon, info in self._monitors.items()]

    def get_monitor_subtitle(self, hmonitor: int, index: int = 0) -> str:
        """Return subtitle like 'Monitor 1' or 'Monitor 1 · DisplayPort'."""
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            conn = monitor.connection_type if monitor else ""
        if conn:
            return f"Monitor {index + 1} · {conn}"
        return f"Monitor {index + 1}"

    # Internal methods
    def _start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="BrightnessService")
        self._thread.start()

    @staticmethod
    def _normalize_monitor_name(name: str, index: int) -> str:
        clean = name.strip()
        if clean and not clean.isdigit():
            return clean
        return f"Monitor {index + 1}"

    def _stop(self) -> None:
        """Stop the background thread and cleanup resources."""
        self._running = False
        if self._lcd_handle:
            kernel32.CloseHandle(self._lcd_handle)
            self._lcd_handle = None

    def _run(self) -> None:
        """Background thread main loop."""
        self._enumerate_monitors()
        logging.debug("BrightnessService started with %d monitors", len(self._monitors))

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
            pending_b = list(self._pending_set.items())
            pending_c = list(self._pending_contrast_set.items())

        for hmonitor, (value, timestamp) in pending_b:
            if now - timestamp < self._set_debounce:
                continue
            with self._lock:
                current = self._pending_set.get(hmonitor)
                if current is None or current[1] != timestamp:
                    continue
                del self._pending_set[hmonitor]
            self._apply_brightness(hmonitor, value)

        for hmonitor, (value, timestamp) in pending_c:
            if now - timestamp < self._set_debounce:
                continue
            with self._lock:
                current = self._pending_contrast_set.get(hmonitor)
                if current is None or current[1] != timestamp:
                    continue
                del self._pending_contrast_set[hmonitor]
            self._vcp_write(hmonitor, VCP_CONTRAST, value)

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
                # Skip cache update if a user-initiated "set" event is pending or just applied;
                # physical reads can lag and would overwrite the newer in‑memory value.
                if hmonitor in self._pending_set:
                    continue
                old_brightness = monitor.brightness
                was_reported = monitor.reported
                monitor.brightness = brightness
                monitor.reported = True

            # Emit on first report or change
            if not was_reported or old_brightness != brightness:
                self.brightness_changed.emit(hmonitor, brightness)

            # Poll contrast for DDC monitors
            with self._lock:
                monitor = self._monitors.get(hmonitor)
                if not monitor or not monitor.supports_ddc or hmonitor in self._pending_contrast_set:
                    continue
                already_tested = monitor.contrast_tested

            contrast = self._vcp_read(hmonitor, VCP_CONTRAST)

            with self._lock:
                monitor = self._monitors.get(hmonitor)
                if monitor:
                    if not already_tested:
                        monitor.contrast_tested = True
                        monitor.supports_contrast = contrast is not None
                    if monitor.supports_contrast and monitor.contrast != contrast:
                        monitor.contrast = contrast
                        self.contrast_changed.emit(hmonitor, contrast)

    def _enumerate_monitors(self) -> None:
        """Enumerate all system monitors."""
        with self._lock:
            self._monitors.clear()
        targets = get_active_display_targets()

        index = [0]

        def enum_callback(hmonitor, hdc, rect, lparam):
            hmon = int(hmonitor)
            info = _MonitorInfo(hmon)
            source_name = get_monitor_info(hmon).get("device", "")
            target = targets.get(source_name) if source_name else None
            info.name = self._get_monitor_name(hmon, index[0], target.monitor_name if target else "")
            info.connection_type = target.connection_type if target else ""
            index[0] += 1
            with self._lock:
                self._monitors[hmon] = info
            logging.debug("BrightnessService found monitor: %s (%s)", hmon, info.name)
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(enum_callback), 0)

    def _get_monitor_name(self, hmonitor: int, index: int, friendly_name: str) -> str:
        """Resolve monitor name with DisplayConfig -> DDC -> 'Monitor N' fallback."""
        normalized = self._normalize_monitor_name(friendly_name, index)
        if normalized != f"Monitor {index + 1}":
            return normalized
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return f"Monitor {index + 1}"
            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return f"Monitor {index + 1}"
            try:
                name = monitors[0].szPhysicalMonitorDescription
                return self._normalize_monitor_name(name or "", index)
            finally:
                self._destroy_physical_monitors(monitors, count.value)
        except Exception:
            return f"Monitor {index + 1}"

    # Brightness read/write operations
    def _read_brightness(self, hmonitor: int) -> int | None:
        """Read current brightness for a monitor."""
        with self._lock:
            if hmonitor not in self._monitors:
                self._monitors[hmonitor] = _MonitorInfo(hmonitor)
            monitor = self._monitors[hmonitor]

        # Test capabilities on first access. LCD is global on the laptop panel
        # so only assign it to one monitor (and only if DDC failed) to avoid
        # external-monitor widgets writing to the laptop panel.
        if not monitor.tested:
            monitor.supports_ddc = self._test_ddc(hmonitor)
            if not monitor.supports_ddc:
                monitor.supports_lcd = self._test_lcd(hmonitor)
            monitor.tested = True
            logging.debug("Monitor %s: DDC=%s, LCD=%s", hmonitor, monitor.supports_ddc, monitor.supports_lcd)

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
    def _destroy_physical_monitors(self, monitors, count: int) -> None:
        """Destroy all physical monitor handles to prevent leaks."""
        for i in range(count):
            handle = monitors[i].hPhysicalMonitor
            if handle is not None:
                try:
                    dxva2.DestroyPhysicalMonitor(handle)
                except Exception:
                    pass

    def _vcp_read(self, hmonitor: int, code: int) -> int | None:
        """Read a VCP value; returns 0-100 percentage or None if unsupported."""
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return None
            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return None
            try:
                handle = monitors[0].hPhysicalMonitor or 0
                current, maximum = DWORD(), DWORD()
                if dxva2.GetVCPFeatureAndVCPFeatureReply(handle, BYTE(code), None, byref(current), byref(maximum)):
                    return round(current.value / max(maximum.value, 1) * 100)
                return None
            finally:
                self._destroy_physical_monitors(monitors, count.value)
        except Exception:
            return None

    def _vcp_write(self, hmonitor: int, code: int, value: int) -> bool:
        """Write a VCP value (0-100 percentage) to the monitor."""
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return False
            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return False
            try:
                handle = monitors[0].hPhysicalMonitor or 0
                current, maximum = DWORD(), DWORD()
                max_val = 100
                if dxva2.GetVCPFeatureAndVCPFeatureReply(handle, BYTE(code), None, byref(current), byref(maximum)):
                    max_val = maximum.value or 100
                native = max(0, min(round(value * max_val / 100), max_val))
                return bool(dxva2.SetVCPFeature(handle, BYTE(code), DWORD(native)))
            finally:
                self._destroy_physical_monitors(monitors, count.value)
        except Exception:
            return False

    def _test_ddc(self, hmonitor: int) -> bool:
        """Test if monitor supports DDC/CI brightness control."""
        try:
            count = DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
                return False

            monitors = (PHYSICAL_MONITOR * count.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
                return False

            try:
                for i in range(count.value):
                    handle = monitors[i].hPhysicalMonitor
                    actual_handle = handle if handle is not None else 0
                    current, maximum = DWORD(), DWORD()
                    for attempt in range(50):
                        if dxva2.GetVCPFeatureAndVCPFeatureReply(
                            actual_handle, BYTE(VCP_BRIGHTNESS), None, byref(current), byref(maximum)
                        ):
                            return True
                        time.sleep(0.02 if attempt < 20 else 0.1)
                return False
            finally:
                self._destroy_physical_monitors(monitors, count.value)
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

            try:
                for i in range(count.value):
                    handle = monitors[i].hPhysicalMonitor
                    actual_handle = handle if handle is not None else 0
                    current, maximum = DWORD(), DWORD()
                    for attempt in range(50):
                        if dxva2.GetVCPFeatureAndVCPFeatureReply(
                            actual_handle, BYTE(VCP_BRIGHTNESS), None, byref(current), byref(maximum)
                        ):
                            return round((current.value / max(maximum.value, 1)) * 100)
                        time.sleep(0.02 if attempt < 20 else 0.1)
                return None
            finally:
                self._destroy_physical_monitors(monitors, count.value)
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

            try:
                for i in range(count.value):
                    handle = monitors[i].hPhysicalMonitor
                    actual_handle = handle if handle is not None else 0

                    # Read the monitor's max VCP value to scale correctly
                    current_val, maximum = DWORD(), DWORD()
                    max_val = 100  # default
                    for attempt in range(50):
                        if dxva2.GetVCPFeatureAndVCPFeatureReply(
                            actual_handle, BYTE(VCP_BRIGHTNESS), None, byref(current_val), byref(maximum)
                        ):
                            max_val = maximum.value if maximum.value > 0 else 100
                            break
                        time.sleep(0.02 if attempt < 20 else 0.1)

                    # Convert percentage (0-100) to monitor's native VCP range
                    native_value = round(value * max_val / 100)
                    native_value = max(0, min(native_value, max_val))

                    for attempt in range(50):
                        if dxva2.SetVCPFeature(actual_handle, BYTE(VCP_BRIGHTNESS), DWORD(native_value)):
                            return True
                        time.sleep(0.02 if attempt < 20 else 0.1)
                return False
            finally:
                self._destroy_physical_monitors(monitors, count.value)
        except Exception:
            return False

    # LCD operations
    def _test_lcd(self, hmonitor: int) -> bool:
        """Test if LCD brightness control is available and claim ownership.

        The LCD device is global (laptop panel) so only one monitor may own it.
        First non-DDC monitor to ask wins; subsequent calls return False.
        """
        if self._lcd_owner is not None:
            return self._lcd_owner == hmonitor

        if not self._lcd_tested:
            self._lcd_tested = True
            try:
                handle = kernel32.CreateFileW("\\\\.\\LCD", 0xC0000000, 0x03, None, 3, 0, None)
                if handle and handle != INVALID_HANDLE_VALUE:
                    self._lcd_handle = handle
                    self._lcd_available = True
            except Exception:
                pass

        if self._lcd_available:
            self._lcd_owner = hmonitor
            return True
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

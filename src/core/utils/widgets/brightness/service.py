"""
Brightness control using native Windows APIs.
Supports laptop screens via WMI and external monitors via DXVA2/DDC-CI.
"""

import ctypes
import logging
from concurrent.futures import ThreadPoolExecutor
from ctypes import POINTER, Structure, byref, windll
from ctypes.wintypes import BOOL, DWORD, HANDLE
from functools import lru_cache

import win32api
from PyQt6.QtCore import QObject, QTimer

from settings import DEBUG


class PHYSICAL_MONITOR(Structure):
    _fields_ = [
        ("hPhysicalMonitor", HANDLE),
        ("szPhysicalMonitorDescription", ctypes.c_wchar * 128),
    ]


@lru_cache(maxsize=1)
def _get_dxva2():
    """Load and configure dxva2.dll for external monitor control."""
    try:
        dxva2 = windll.dxva2
        dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [HANDLE, POINTER(DWORD)]
        dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = BOOL
        dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [HANDLE, DWORD, POINTER(PHYSICAL_MONITOR)]
        dxva2.GetPhysicalMonitorsFromHMONITOR.restype = BOOL
        dxva2.DestroyPhysicalMonitors.argtypes = [DWORD, POINTER(PHYSICAL_MONITOR)]
        dxva2.DestroyPhysicalMonitors.restype = BOOL
        dxva2.GetMonitorBrightness.argtypes = [HANDLE, POINTER(DWORD), POINTER(DWORD), POINTER(DWORD)]
        dxva2.GetMonitorBrightness.restype = BOOL
        dxva2.SetMonitorBrightness.argtypes = [HANDLE, DWORD]
        dxva2.SetMonitorBrightness.restype = BOOL
        return dxva2
    except OSError:
        return None


def _get_physical_monitors(hmonitor: int):
    """Get physical monitor handles from a display."""
    dxva2 = _get_dxva2()
    if not dxva2:
        return None, 0
    try:
        count = DWORD()
        if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
            return None, 0
        pm_array = (PHYSICAL_MONITOR * count.value)()
        if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, pm_array):
            return None, 0
        return pm_array, count.value
    except Exception:
        return None, 0


def _destroy_physical_monitors(pm_array, count: int):
    """Clean up monitor handles when done."""
    if pm_array and count > 0:
        try:
            dxva2 = _get_dxva2()
            if dxva2:
                dxva2.DestroyPhysicalMonitors(count, pm_array)
        except Exception:
            pass


class BrightnessOps:
    """Low-level brightness operations for WMI and DXVA2."""

    _wmi_service = None
    _wmi_checked = False
    _brightness_range: dict[int, tuple[int, int]] = {}

    @classmethod
    def _init_wmi(cls):
        """Set up WMI connection for laptop brightness."""
        if cls._wmi_checked:
            return cls._wmi_service is not None
        cls._wmi_checked = True
        try:
            import comtypes.client

            cls._wmi_service = comtypes.client.CoGetObject("winmgmts:root/wmi")
            result = cls._wmi_service.ExecQuery("SELECT * FROM WmiMonitorBrightness")
            if len(list(result)) == 0:
                cls._wmi_service = None
        except Exception as e:
            cls._wmi_service = None
            if DEBUG:
                logging.debug(f"WMI not available: {e}")
        return cls._wmi_service is not None

    @classmethod
    def get_wmi_brightness(cls) -> int | None:
        """Read current brightness from a laptop screen."""
        if not cls._init_wmi():
            return None
        try:
            result = cls._wmi_service.ExecQuery("SELECT CurrentBrightness FROM WmiMonitorBrightness WHERE Active=TRUE")
            for monitor in result:
                return monitor.CurrentBrightness
        except Exception:
            pass
        return None

    @classmethod
    def set_wmi_brightness(cls, value: int) -> bool:
        """Change brightness on a laptop screen."""
        if not cls._init_wmi():
            return False
        try:
            result = cls._wmi_service.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods WHERE Active=TRUE")
            for monitor in result:
                monitor.WmiSetBrightness(value, 0)
                return True
        except Exception:
            pass
        return False

    @classmethod
    def get_dxva2_brightness(cls, hmonitor: int) -> int | None:
        """Read current brightness from an external monitor."""
        dxva2 = _get_dxva2()
        if not dxva2:
            return None
        pm_array, count = _get_physical_monitors(hmonitor)
        if not pm_array:
            return None
        try:
            min_b, cur_b, max_b = DWORD(), DWORD(), DWORD()
            if not dxva2.GetMonitorBrightness(pm_array[0].hPhysicalMonitor, byref(min_b), byref(cur_b), byref(max_b)):
                return None
            cls._brightness_range[hmonitor] = (min_b.value, max_b.value)
            if max_b.value > min_b.value:
                return int(((cur_b.value - min_b.value) / (max_b.value - min_b.value)) * 100)
            return cur_b.value
        except Exception:
            return None
        finally:
            _destroy_physical_monitors(pm_array, count)

    @classmethod
    def set_dxva2_brightness(cls, hmonitor: int, value: int) -> bool:
        """Change brightness on an external monitor."""
        dxva2 = _get_dxva2()
        if not dxva2:
            return False
        pm_array, count = _get_physical_monitors(hmonitor)
        if not pm_array:
            return False
        try:
            # Get range if not cached
            if hmonitor not in cls._brightness_range:
                min_b, cur_b, max_b = DWORD(), DWORD(), DWORD()
                if not dxva2.GetMonitorBrightness(
                    pm_array[0].hPhysicalMonitor, byref(min_b), byref(cur_b), byref(max_b)
                ):
                    return False
                cls._brightness_range[hmonitor] = (min_b.value, max_b.value)

            min_val, max_val = cls._brightness_range[hmonitor]
            native_value = int(min_val + (value / 100) * (max_val - min_val)) if max_val > min_val else value
            return bool(dxva2.SetMonitorBrightness(pm_array[0].hPhysicalMonitor, native_value))
        except Exception:
            return False
        finally:
            _destroy_physical_monitors(pm_array, count)


class BrightnessService(QObject):
    """Main service that manages brightness for all widgets."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        super().__init__()

        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Brightness")
        self._widgets: dict[int, object] = {}
        self._method_cache: dict[int, str] = {}  # hmonitor -> "wmi" | "dxva2" | "none"
        self._last_brightness: dict[int, int] = {}
        self._poll_timer: QTimer | None = None
        self._pending_results: list = []
        self._result_timer: QTimer | None = None

    def _start_result_timer(self):
        """Start checking for brightness updates."""
        if self._result_timer is None:
            self._result_timer = QTimer()
            self._result_timer.timeout.connect(self._check_results)
            self._result_timer.start(50)

    def _check_results(self):
        """Deliver brightness values to widgets when ready."""
        still_pending = []
        for future, widget_id, hmonitor in self._pending_results:
            if future.done():
                try:
                    brightness = future.result()
                    if brightness is not None and self._last_brightness.get(hmonitor) != brightness:
                        self._last_brightness[hmonitor] = brightness
                        widget = self._widgets.get(widget_id)
                        if widget:
                            widget.on_brightness_changed(brightness)
                except Exception:
                    pass
            else:
                still_pending.append((future, widget_id, hmonitor))
        self._pending_results = still_pending

    def _detect_method(self, hmonitor: int) -> str:
        """Figure out which API works for this monitor."""
        if hmonitor in self._method_cache:
            return self._method_cache[hmonitor]

        # Try WMI for primary/laptop
        try:
            primary = int(win32api.MonitorFromPoint((0, 0), 1))
            if hmonitor == primary and BrightnessOps._init_wmi():
                self._method_cache[hmonitor] = "wmi"
                return "wmi"
        except Exception:
            pass

        # Try DXVA2
        if BrightnessOps.get_dxva2_brightness(hmonitor) is not None:
            self._method_cache[hmonitor] = "dxva2"
            return "dxva2"

        self._method_cache[hmonitor] = "none"
        return "none"

    def _do_get_brightness(self, hmonitor: int) -> int | None:
        """Read brightness from the monitor."""
        method = self._detect_method(hmonitor)
        if method == "wmi":
            return BrightnessOps.get_wmi_brightness()
        elif method == "dxva2":
            return BrightnessOps.get_dxva2_brightness(hmonitor)
        return None

    def _do_set_brightness(self, hmonitor: int, value: int):
        """Apply brightness to the monitor."""
        value = max(0, min(100, value))
        method = self._detect_method(hmonitor)
        if method == "wmi":
            BrightnessOps.set_wmi_brightness(value)
        elif method == "dxva2":
            BrightnessOps.set_dxva2_brightness(hmonitor, value)

    def get_brightness(self, hmonitor: int, widget) -> None:
        """Request current brightness level."""
        if not hmonitor:
            return
        self._start_result_timer()
        future = self._executor.submit(self._do_get_brightness, hmonitor)
        self._pending_results.append((future, id(widget), hmonitor))

    def set_brightness(self, hmonitor: int, value: int) -> None:
        """Change brightness to the specified level."""
        if hmonitor:
            self._executor.submit(self._do_set_brightness, hmonitor, value)

    def clear_cache(self) -> None:
        """Reset stored brightness data."""
        self._method_cache.clear()
        self._last_brightness.clear()
        BrightnessOps._brightness_range.clear()

    def register_widget(self, widget) -> None:
        """Add a widget to receive brightness updates."""
        self._widgets[id(widget)] = widget
        if self._poll_timer is None:
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._poll)
            self._poll_timer.start(5000)  # Poll every 5 seconds

    def unregister_widget(self, widget) -> None:
        """Remove a widget from updates."""
        self._widgets.pop(id(widget), None)
        if not self._widgets and self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
            self._poll_timer = None

    def _poll(self) -> None:
        """Check brightness for all active widgets."""
        for widget_id, widget in list(self._widgets.items()):
            hmonitor = widget.get_hmonitor()
            if hmonitor and self._method_cache.get(hmonitor) != "none":
                future = self._executor.submit(self._do_get_brightness, hmonitor)
                self._pending_results.append((future, widget_id, hmonitor))

    def shutdown(self) -> None:
        """Stop the service and clean up."""
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None
        if self._result_timer:
            self._result_timer.stop()
            self._result_timer = None
        self._executor.shutdown(wait=False)

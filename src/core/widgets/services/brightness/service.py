import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from ctypes import POINTER, Structure, addressof, byref, c_byte, cast, string_at
from ctypes.wintypes import BYTE, DWORD, HWND, MSG
from typing import ClassVar

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.qobject import is_valid_qobject
from core.utils.win32.bindings.dxva2 import PHYSICAL_MONITOR, VCP_BRIGHTNESS, VCP_CONTRAST, dxva2
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.user32 import MONITORENUMPROC, user32
from core.utils.win32.structs import GUID, WNDCLASS, WNDPROC
from core.utils.win32.utils import get_monitor_info
from core.widgets.services.brightness.displays import query_display
from core.widgets.services.brightness.scheme import (
    get_scheme_brightness,
    policy_brightness_guid,
    set_scheme_brightness,
)

WM_POWERBROADCAST = 0x0218
WM_QUIT = 0x0012
PBT_POWERSETTINGCHANGE = 0x8013
DEVICE_NOTIFY_WINDOW_HANDLE = 0
HWND_MESSAGE = HWND(-3)
DDC_ATTEMPTS = 5
DDC_RETRY_SLEEP = 0.1


class POWERBROADCAST_SETTING(Structure):
    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", DWORD),
        ("Data", c_byte * 1),
    ]


class _MonitorInfo:
    __slots__ = (
        "hmonitor",
        "device",
        "supports_ddc",
        "supports_scheme",
        "brightness",
        "tested",
        "reported",
        "name",
        "connection_type",
        "is_internal",
        "contrast",
        "supports_contrast",
        "contrast_tested",
    )

    def __init__(self, hmonitor: int) -> None:
        self.hmonitor = hmonitor
        self.device = ""
        self.supports_ddc = False
        self.supports_scheme = False
        self.brightness: int | None = None
        self.tested = False
        self.reported = False
        self.name: str = ""
        self.connection_type: str = ""
        self.is_internal = False
        self.contrast: int | None = None
        self.supports_contrast: bool = False
        self.contrast_tested: bool = False


class BrightnessService(QObject):
    """Singleton service for monitor brightness control."""

    _instance: ClassVar[BrightnessService | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    brightness_changed = pyqtSignal(int, object)
    contrast_changed = pyqtSignal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self._monitors: dict[int, _MonitorInfo] = {}
        self._scheme_owner: int | None = None
        self._running = False
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._ignore_policy_until = 0.0

        self._want_brightness: dict[int, int] = {}
        self._want_contrast: dict[int, int] = {}
        self._writing = False
        self._refreshing = False
        self._ddc_poll_interval = 0

        self._policy_thread_id = 0
        self._policy_hwnd: int | None = None
        self._policy_notify = None
        self._wndproc_ref = None
        self._policy_guid = policy_brightness_guid()

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop)

    @classmethod
    def instance(cls, ddc_poll_interval: int = 60) -> BrightnessService:
        """Shared singleton. First caller sets ddc_poll_interval."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._ddc_poll_interval = ddc_poll_interval
                    cls._instance._start()
        return cls._instance

    def get_brightness(self, hmonitor: int) -> int | None:
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            return monitor.brightness if monitor else None

    def set_brightness(self, hmonitor: int, value: int) -> None:
        value = max(0, min(100, value))
        should_emit = False
        start_writer = False
        with self._lock:
            self._want_brightness[hmonitor] = value
            if hmonitor in self._monitors:
                monitor = self._monitors[hmonitor]
                should_emit = monitor.brightness != value or not monitor.reported
                monitor.brightness = value
                monitor.reported = True
            if not self._writing:
                self._writing = True
                start_writer = True

        if should_emit:
            self.brightness_changed.emit(hmonitor, value)
        if start_writer:
            threading.Thread(target=self._drain_writes, daemon=True, name="BrightnessWrite").start()

    def get_contrast(self, hmonitor: int) -> int | None:
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            return monitor.contrast if monitor else None

    def set_contrast(self, hmonitor: int, value: int) -> None:
        value = max(0, min(100, value))
        start_writer = False
        with self._lock:
            self._want_contrast[hmonitor] = value
            if hmonitor in self._monitors:
                self._monitors[hmonitor].contrast = value
            if not self._writing:
                self._writing = True
                start_writer = True
        if start_writer:
            threading.Thread(target=self._drain_writes, daemon=True, name="BrightnessWrite").start()

    def supports_contrast(self, hmonitor: int) -> bool:
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            return monitor.supports_contrast if monitor else False

    def get_monitors(self) -> list[tuple[int, str]]:
        """Controllable monitors only, DDC externals or internal scheme panel."""
        with self._lock:
            return [
                (hmon, info.name) for hmon, info in self._monitors.items() if info.supports_ddc or info.supports_scheme
            ]

    def get_monitor_subtitle(self, hmonitor: int, index: int = 0) -> str:
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            conn = monitor.connection_type if monitor else ""
        if conn:
            return f"Monitor {index + 1} · {conn}"
        return f"Monitor {index + 1}"

    def refresh_now(self, hmonitor: int | None = None) -> None:
        """Refresh DDC monitors in the background. Scheme uses POLICY cache."""
        with self._lock:
            if self._refreshing:
                return
            if hmonitor is not None:
                mon = self._monitors.get(hmonitor)
                if not mon or not mon.supports_ddc:
                    return
            elif not any(m.tested and m.supports_ddc for m in self._monitors.values()):
                return
            self._refreshing = True
        threading.Thread(
            target=self._refresh_now_bg,
            args=(hmonitor,),
            daemon=True,
            name="BrightnessRefresh",
        ).start()

    def _refresh_now_bg(self, hmonitor: int | None) -> None:
        try:
            with self._lock:
                if hmonitor is not None:
                    mon = self._monitors.get(hmonitor)
                    targets = [hmonitor] if mon and mon.supports_ddc else []
                else:
                    targets = [h for h, m in self._monitors.items() if m.tested and m.supports_ddc]
            if not targets:
                return
            workers = min(len(targets), 4)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="BrightnessRefresh") as pool:
                list(pool.map(self._refresh_monitor, targets))
        finally:
            with self._lock:
                self._refreshing = False

    def _start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stopped.clear()
        self._enumerate_monitors()
        logging.info("BrightnessService started with %d monitors", len(self._monitors))
        threading.Thread(target=self._detect_capabilities_parallel, daemon=True, name="BrightnessDetect").start()
        threading.Thread(target=self._policy_message_loop, daemon=True, name="BrightnessPolicy").start()
        threading.Thread(target=self._ddc_poll_loop, daemon=True, name="BrightnessDDCPoll").start()

    def _stop(self) -> None:
        self._running = False
        self._stopped.set()
        if self._policy_thread_id:
            user32.PostThreadMessageW(self._policy_thread_id, WM_QUIT, 0, 0)

    @staticmethod
    def _normalize_monitor_name(name: str, index: int) -> str:
        clean = name.strip()
        if clean and not clean.isdigit():
            return clean
        return f"Monitor {index + 1}"

    def _drain_writes(self) -> None:
        """Apply latest slider values (keeps only the newest per monitor)."""
        try:
            while self._running:
                with self._lock:
                    brightness = self._want_brightness
                    contrast = self._want_contrast
                    self._want_brightness = {}
                    self._want_contrast = {}
                    if not brightness and not contrast:
                        break
                for hmonitor, value in brightness.items():
                    self._apply_brightness(hmonitor, value)
                for hmonitor, value in contrast.items():
                    self._vcp_write(hmonitor, VCP_CONTRAST, value)
        finally:
            with self._lock:
                if self._running and (self._want_brightness or self._want_contrast):
                    threading.Thread(target=self._drain_writes, daemon=True, name="BrightnessWrite").start()
                else:
                    self._writing = False

    def _ddc_poll_loop(self) -> None:
        while not self._stopped.is_set():
            with self._lock:
                pending = any(not m.tested for m in self._monitors.values())
                has_ddc = any(m.tested and m.supports_ddc for m in self._monitors.values())
            if pending:
                self._stopped.wait(0.2)
                continue
            if self._ddc_poll_interval == 0 or not has_ddc:
                break
            if self._stopped.wait(self._ddc_poll_interval):
                break
            with self._lock:
                hmonitors = [h for h, m in self._monitors.items() if m.tested and m.supports_ddc]
            for hmonitor in hmonitors:
                self._refresh_monitor(hmonitor)

    def _policy_message_loop(self) -> None:
        """Listen for GUID_DEVICE_POWER_POLICY_VIDEO_BRIGHTNESS changes."""
        self._policy_thread_id = kernel32.GetCurrentThreadId()
        class_name = "YasbBrightnessPolicyWatcher"
        self._wndproc_ref = WNDPROC(self._policy_wnd_proc)

        wc = WNDCLASS()
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = class_name
        if not user32.RegisterClassW(byref(wc)) and kernel32.GetLastError() not in (0, 1410):
            logging.debug("BrightnessService: RegisterClassW failed")
            return

        hwnd = user32.CreateWindowExW(
            0, class_name, "YASB brightness policy", 0, 0, 0, 0, 0, HWND_MESSAGE, None, wc.hInstance, None
        )
        if not hwnd:
            logging.debug("BrightnessService: CreateWindowExW failed")
            return
        self._policy_hwnd = int(hwnd)

        notify = user32.RegisterPowerSettingNotification(hwnd, byref(self._policy_guid), DEVICE_NOTIFY_WINDOW_HANDLE)
        if not notify:
            logging.debug("BrightnessService: RegisterPowerSettingNotification failed")
            user32.DestroyWindow(hwnd)
            self._policy_hwnd = None
            return
        self._policy_notify = notify

        try:
            msg = MSG()
            while True:
                result = user32.GetMessageW(byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                user32.TranslateMessage(byref(msg))
                user32.DispatchMessageW(byref(msg))
        finally:
            if self._policy_notify:
                user32.UnregisterPowerSettingNotification(self._policy_notify)
                self._policy_notify = None
            if self._policy_hwnd:
                user32.DestroyWindow(self._policy_hwnd)
                self._policy_hwnd = None
            self._policy_thread_id = 0

    def _policy_wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_POWERBROADCAST and int(wparam) == PBT_POWERSETTINGCHANGE and lparam:
            if time.monotonic() < self._ignore_policy_until:
                return 1
            setting = cast(lparam, POINTER(POWERBROADCAST_SETTING)).contents
            raw = string_at(addressof(setting.Data), setting.DataLength)
            value = max(0, min(100, int.from_bytes(raw[:4].ljust(4, b"\x00"), "little")))
            owner = self._scheme_owner
            if owner is None:
                return 1
            with self._lock:
                monitor = self._monitors.get(owner)
                if not monitor or not monitor.supports_scheme:
                    return 1
                if owner in self._want_brightness:
                    return 1
                old = monitor.brightness
                was_reported = monitor.reported
                monitor.brightness = value
                monitor.reported = True
            if (not was_reported or old != value) and is_valid_qobject(self) and self._running:
                self.brightness_changed.emit(owner, value)
            return 1
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _detect_capabilities_parallel(self) -> None:
        self._enrich_display_metadata()
        with self._lock:
            hmonitors = list(self._monitors.keys())
        if not hmonitors:
            return

        pending_scheme: list[int] = []
        with ThreadPoolExecutor(max_workers=len(hmonitors), thread_name_prefix="BrightnessDDC") as pool:
            futures = {pool.submit(self._test_ddc, hmon): hmon for hmon in hmonitors}
            for future in as_completed(futures):
                hmonitor = futures[future]
                try:
                    supports_ddc = future.result()
                except Exception:
                    supports_ddc = False

                if supports_ddc:
                    with self._lock:
                        monitor = self._monitors.get(hmonitor)
                        if not monitor or monitor.tested:
                            continue
                        # Duplicate/mirror: one HMONITOR can expose DDC on the
                        # external while WinRT still marks INTERNAL. Prefer scheme.
                        if monitor.is_internal:
                            logging.debug(
                                "Monitor %s: DDC ignored (internal) using scheme",
                                hmonitor,
                            )
                            pending_scheme.append(hmonitor)
                            continue
                        monitor.supports_ddc = True
                        monitor.tested = True
                        logging.debug("Monitor %s: DDC=True scheme=False", hmonitor)
                    brightness = self._vcp_read(hmonitor, VCP_BRIGHTNESS)
                    if brightness is not None:
                        with self._lock:
                            self._monitors[hmonitor].brightness = brightness
                            self._monitors[hmonitor].reported = True
                        self.brightness_changed.emit(hmonitor, brightness)
                    contrast = self._vcp_read(hmonitor, VCP_CONTRAST)
                    with self._lock:
                        monitor = self._monitors.get(hmonitor)
                        if monitor and not monitor.contrast_tested:
                            monitor.contrast_tested = True
                            monitor.supports_contrast = contrast is not None
                            if contrast is not None:
                                monitor.contrast = contrast
                    if contrast is not None and is_valid_qobject(self) and self._running:
                        self.contrast_changed.emit(hmonitor, contrast)
                else:
                    pending_scheme.append(hmonitor)

        for hmonitor in pending_scheme:
            can_scheme = False
            with self._lock:
                monitor = self._monitors.get(hmonitor)
                if not monitor or monitor.tested:
                    continue
                # Scheme only for INTERNAL panels
                can_scheme = monitor.is_internal and self._claim_scheme_owner(hmonitor)
                monitor.supports_scheme = can_scheme
                monitor.tested = True
                logging.debug(
                    "Monitor %s: DDC=False scheme=%s internal=%s name=%s",
                    hmonitor,
                    monitor.supports_scheme,
                    monitor.is_internal,
                    monitor.name,
                )
            if not can_scheme:
                continue
            brightness = get_scheme_brightness()
            if brightness is not None:
                with self._lock:
                    self._monitors[hmonitor].brightness = brightness
                    self._monitors[hmonitor].reported = True
                self.brightness_changed.emit(hmonitor, brightness)

    def _enrich_display_metadata(self) -> None:
        """WinRT lookup."""
        with self._lock:
            monitors = [(hmon, info.device) for hmon, info in self._monitors.items()]
        for index, (hmon, device) in enumerate(monitors):
            target = query_display(device)
            if target.monitor_name:
                name = target.monitor_name
            elif target.is_internal:
                name = "Built-in display"
            else:
                name = self._get_monitor_name(hmon, index)
            if target.is_internal and name.startswith("Monitor "):
                name = "Built-in display"
            with self._lock:
                monitor = self._monitors.get(hmon)
                if not monitor:
                    continue
                monitor.name = name
                monitor.connection_type = target.connection_type
                monitor.is_internal = target.is_internal
            logging.debug(
                "Monitor %s metadata: %s internal=%s conn=%s",
                hmon,
                name,
                target.is_internal,
                target.connection_type,
            )

    def _claim_scheme_owner(self, hmonitor: int) -> bool:
        """Assign power-scheme brightness to one internal panel."""
        if self._scheme_owner is not None:
            return self._scheme_owner == hmonitor
        if get_scheme_brightness() is None:
            return False
        self._scheme_owner = hmonitor
        return True

    def _refresh_monitor(self, hmonitor: int) -> None:
        brightness = self._read_brightness(hmonitor)
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            if not monitor or hmonitor in self._want_brightness:
                return
            old_brightness = monitor.brightness
            was_reported = monitor.reported
            monitor.brightness = brightness
            monitor.reported = True
            supports_ddc = monitor.supports_ddc
            already_tested = monitor.contrast_tested

        if (not was_reported or old_brightness != brightness) and is_valid_qobject(self) and self._running:
            self.brightness_changed.emit(hmonitor, brightness)

        if not supports_ddc:
            return
        with self._lock:
            if hmonitor in self._want_contrast:
                return

        contrast = self._vcp_read(hmonitor, VCP_CONTRAST)
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            if not monitor:
                return
            if not already_tested:
                monitor.contrast_tested = True
                monitor.supports_contrast = contrast is not None
            if monitor.supports_contrast and monitor.contrast != contrast:
                monitor.contrast = contrast
                if is_valid_qobject(self) and self._running:
                    self.contrast_changed.emit(hmonitor, contrast)

    def _enumerate_monitors(self) -> None:
        """Fast HMONITOR scan only"""
        with self._lock:
            self._monitors.clear()
            self._scheme_owner = None
        index = [0]

        def enum_callback(hmonitor, hdc, rect, lparam):
            hmon = int(hmonitor)
            info = _MonitorInfo(hmon)
            info.device = get_monitor_info(hmon).get("device", "")
            info.name = f"Monitor {index[0] + 1}"
            index[0] += 1
            with self._lock:
                self._monitors[hmon] = info
            logging.debug("BrightnessService found monitor: %s device=%s", hmon, info.device)
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(enum_callback), 0)

    def _get_monitor_name(self, hmonitor: int, index: int) -> str:
        try:
            opened = self._open_physical(hmonitor)
            if opened is None:
                return f"Monitor {index + 1}"
            monitors, count = opened
            try:
                return self._normalize_monitor_name(monitors[0].szPhysicalMonitorDescription or "", index)
            finally:
                self._destroy_physical_monitors(monitors, count)
        except Exception:
            return f"Monitor {index + 1}"

    def _read_brightness(self, hmonitor: int) -> int | None:
        """Read brightness for an already-classified monitor. Detection owns classification."""
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            if not monitor:
                return None
            if not monitor.tested:
                return monitor.brightness
            supports_ddc = monitor.supports_ddc
            supports_scheme = monitor.supports_scheme

        if supports_ddc:
            return self._vcp_read(hmonitor, VCP_BRIGHTNESS)
        if supports_scheme:
            return get_scheme_brightness()
        return None

    def _apply_brightness(self, hmonitor: int, value: int) -> bool:
        with self._lock:
            monitor = self._monitors.get(hmonitor)
            if not monitor or not monitor.tested:
                return False
            supports_ddc = monitor.supports_ddc
            supports_scheme = monitor.supports_scheme

        if supports_ddc and self._vcp_write(hmonitor, VCP_BRIGHTNESS, value):
            return True
        if supports_scheme:
            self._ignore_policy_until = time.monotonic() + 0.5
            return set_scheme_brightness(value)
        return False

    def _destroy_physical_monitors(self, monitors, count: int) -> None:
        for i in range(count):
            handle = monitors[i].hPhysicalMonitor
            if handle is not None:
                try:
                    dxva2.DestroyPhysicalMonitor(handle)
                except Exception:
                    pass

    def _open_physical(self, hmonitor: int):
        count = DWORD()
        if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, byref(count)) or count.value == 0:
            return None
        monitors = (PHYSICAL_MONITOR * count.value)()
        if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
            return None
        return monitors, count.value

    def _test_ddc(self, hmonitor: int) -> bool:
        return self._vcp_read(hmonitor, VCP_BRIGHTNESS) is not None

    def _vcp_read(self, hmonitor: int, code: int) -> int | None:
        try:
            opened = self._open_physical(hmonitor)
            if opened is None:
                return None
            monitors, count = opened
            try:
                for i in range(count):
                    handle = monitors[i].hPhysicalMonitor or 0
                    current, maximum = DWORD(), DWORD()
                    for attempt in range(DDC_ATTEMPTS):
                        if dxva2.GetVCPFeatureAndVCPFeatureReply(
                            handle, BYTE(code), None, byref(current), byref(maximum)
                        ):
                            return round(current.value / max(maximum.value, 1) * 100)
                        if attempt + 1 < DDC_ATTEMPTS:
                            time.sleep(DDC_RETRY_SLEEP)
                return None
            finally:
                self._destroy_physical_monitors(monitors, count)
        except Exception:
            return None

    def _vcp_write(self, hmonitor: int, code: int, value: int) -> bool:
        try:
            opened = self._open_physical(hmonitor)
            if opened is None:
                return False
            monitors, count = opened
            try:
                any_ok = False
                for i in range(count):
                    handle = monitors[i].hPhysicalMonitor or 0
                    current, maximum = DWORD(), DWORD()
                    max_val = 100
                    for attempt in range(DDC_ATTEMPTS):
                        if dxva2.GetVCPFeatureAndVCPFeatureReply(
                            handle, BYTE(code), None, byref(current), byref(maximum)
                        ):
                            max_val = maximum.value or 100
                            break
                        if attempt + 1 < DDC_ATTEMPTS:
                            time.sleep(DDC_RETRY_SLEEP)
                    native = max(0, min(round(value * max_val / 100), max_val))
                    for attempt in range(DDC_ATTEMPTS):
                        if dxva2.SetVCPFeature(handle, BYTE(code), DWORD(native)):
                            any_ok = True
                            break
                        if attempt + 1 < DDC_ATTEMPTS:
                            time.sleep(DDC_RETRY_SLEEP)
                return any_ok
            finally:
                self._destroy_physical_monitors(monitors, count)
        except Exception:
            return False

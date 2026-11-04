import ctypes
import logging
import os
import winreg
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.user32 import user32
from core.utils.win32.constants import (
    KLF_ACTIVATE,
    LOCALE_NAME_MAX_LENGTH,
    LOCALE_SCOUNTRY,
    LOCALE_SISO639LANGNAME,
    LOCALE_SISO639LANGNAME2,
    LOCALE_SISO3166CTRYNAME,
    LOCALE_SLANGUAGE,
    LOCALE_SNAME,
    LOCALE_SNATIVECTRYNAME,
    LOCALE_SNATIVELANGNAME,
    VK_CAPITAL,
    WM_INPUTLANGCHANGEREQUEST,
)
from core.utils.win32.registry_keys import KEYBOARD_LAYOUTS_KEY

MIN_INTERVAL_MS = 250
MAX_INTERVAL_MS = 3600000
# Shell windows cannot receive keyboard input, so switch the current thread's layout instead.
SHELL_CLASSES = ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")


def _locale_info(locale_id: int, kind: int) -> str:
    buffer = ctypes.create_unicode_buffer(LOCALE_NAME_MAX_LENGTH)
    if not kernel32.GetLocaleInfoW(locale_id, kind, buffer, LOCALE_NAME_MAX_LENGTH):
        return ""
    return buffer.value


def language_info(hkl: int) -> dict[str, str]:
    """Return language and layout fields for label placeholders."""
    lang_id = hkl & 0xFFFF
    layout_id = (hkl >> 16) & 0xFFFF
    language_code = _locale_info(lang_id, LOCALE_SISO639LANGNAME)
    return {
        "language_code": language_code,
        "iso_language_code": _locale_info(lang_id, LOCALE_SISO639LANGNAME2) or language_code,
        "country_code": _locale_info(lang_id, LOCALE_SISO3166CTRYNAME),
        "full_name": _locale_info(lang_id, LOCALE_SLANGUAGE),
        "native_country_name": _locale_info(lang_id, LOCALE_SNATIVECTRYNAME),
        "native_lang_name": _locale_info(lang_id, LOCALE_SNATIVELANGNAME),
        "layout_name": _locale_info(layout_id, LOCALE_SNAME),
        "full_layout_name": _locale_info(layout_id, LOCALE_SLANGUAGE),
        "layout_country_name": _locale_info(layout_id, LOCALE_SCOUNTRY),
    }


def installed_layouts() -> list[int]:
    count = user32.GetKeyboardLayoutList(0, None)
    if count <= 0:
        return []
    handles = (ctypes.c_void_p * count)()
    count = user32.GetKeyboardLayoutList(count, handles)
    return list(dict.fromkeys(handle for handle in handles[:count] if handle))


def layout_klid(hkl: int) -> str:
    """Return `hkl`'s registry layout ID, such as `00000409`, without activating it."""
    device = (hkl >> 16) & 0xFFFF
    # An input method editor has its own layout ID.
    if device & 0xF000 == 0xE000:
        return f"{hkl & 0xFFFFFFFF:08X}"
    # Variants such as Dvorak use the registry's Layout Id value.
    if device & 0xF000 == 0xF000:
        layout_id = f"{device & 0x0FFF:04x}"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, KEYBOARD_LAYOUTS_KEY) as layouts:
                index = 0
                while True:
                    try:
                        klid = winreg.EnumKey(layouts, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        with winreg.OpenKey(layouts, klid) as key:
                            if str(winreg.QueryValueEx(key, "Layout Id")[0]).lower() == layout_id:
                                return klid.upper()
                    except OSError:
                        continue
        except OSError:
            pass
        return ""
    return f"{device:08X}"


def layout_text(klid: str) -> str:
    if not klid:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{KEYBOARD_LAYOUTS_KEY}\\{klid}") as key:
            return str(winreg.QueryValueEx(key, "Layout Text")[0])
    except OSError:
        return ""


def foreground_layout() -> tuple[int, int]:
    """Return the foreground HWND and its thread's layout, or 0 for YASB windows."""
    hwnd = user32.GetForegroundWindow() or 0
    pid = ctypes.c_ulong()
    thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    # Keep the previous foreground layout while a YASB window has focus.
    if hwnd and pid.value == os.getpid():
        return hwnd, 0
    return hwnd, user32.GetKeyboardLayout(thread_id) or 0


def caps_lock_on() -> bool:
    return bool(user32.GetKeyState(VK_CAPITAL) & 0x0001)


class KeyboardLanguage(QObject):
    """Manage the foreground input language, installed layouts, and switching."""

    languageChanged = pyqtSignal()
    capsLockChanged = pyqtSignal()
    layoutsChanged = pyqtSignal()
    updateIntervalChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._hkl = 0
        self._language: dict[str, str] = {}
        self._caps_lock = False
        self._handles: list[int] = []
        self._layouts: list[dict[str, Any]] = []
        self._target_window = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _get_update_interval(self) -> int:
        return self._timer.interval()

    def _set_update_interval(self, value: int) -> None:
        value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value != self._timer.interval():
            self._timer.setInterval(value)
            self.updateIntervalChanged.emit()

    # Milliseconds between reads of the language and caps lock
    updateInterval = pyqtProperty(int, _get_update_interval, _set_update_interval, notify=updateIntervalChanged)

    # Keys: language_code, iso_language_code, country_code, full_name, native_country_name, native_lang_name,
    # layout_name, full_layout_name, layout_country_name. Empty when no foreground layout is available.
    @qml_property("QVariantMap", notify=languageChanged)
    def language(self) -> dict[str, str]:
        return self._language

    @qml_property(bool, notify=capsLockChanged)
    def capsLock(self) -> bool:
        return self._caps_lock

    # Layouts: [{id, name, code, layout, current}], sorted by language name. id is the handle in hex.
    @qml_property("QVariantList", notify=layoutsChanged)
    def layouts(self) -> list[dict[str, Any]]:
        return self._layouts

    @pyqtSlot()
    def refresh(self) -> None:
        caps_lock = caps_lock_on()
        if caps_lock != self._caps_lock:
            self._caps_lock = caps_lock
            self.capsLockChanged.emit()
        handles = installed_layouts()
        if handles != self._handles:
            self._handles = handles
            self._read_layouts()
        _, hkl = foreground_layout()
        if hkl:
            self._set_layout(hkl)

    def _set_layout(self, hkl: int) -> None:
        if hkl == self._hkl:
            return
        self._hkl = hkl
        self._language = language_info(hkl)
        self.languageChanged.emit()
        self._mark_current()

    def _read_layouts(self) -> None:
        layouts: list[dict[str, Any]] = []
        for hkl in self._handles:
            info = language_info(hkl)
            if not info["full_name"]:
                continue
            layouts.append(
                {
                    "id": f"{hkl:x}",
                    "name": info["full_name"],
                    "code": info["iso_language_code"].upper(),
                    "layout": layout_text(layout_klid(hkl)) or info["full_name"],
                    "current": hkl == self._hkl,
                }
            )
        self._layouts = sorted(layouts, key=lambda layout: layout["name"])
        self.layoutsChanged.emit()

    def _mark_current(self) -> None:
        current = f"{self._hkl:x}"
        if any(layout["current"] != (layout["id"] == current) for layout in self._layouts):
            self._layouts = [{**layout, "current": layout["id"] == current} for layout in self._layouts]
            self.layoutsChanged.emit()

    # Remember the target window before the menu takes focus.
    @pyqtSlot()
    def rememberWindow(self) -> None:
        self._target_window, _ = foreground_layout()

    @pyqtSlot(str)
    def activate(self, layout_id: str) -> None:
        try:
            hkl = int(layout_id, 16)
        except ValueError:
            return
        if hkl not in self._handles:
            logging.error("Keyboard layout %s is not installed", layout_id)
            return
        window = self._target_window
        if window and user32.IsWindow(window) and _class_name(window) not in SHELL_CLASSES:
            user32.SetForegroundWindow(window)
            user32.PostMessageW(window, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        elif not user32.ActivateKeyboardLayout(ctypes.c_void_p(hkl), 0):
            if not user32.LoadKeyboardLayoutW(layout_klid(hkl), KLF_ACTIVATE):
                logging.error("Could not switch to keyboard layout %s", layout_id)
                return
        # Update the label before the target window processes the layout request.
        self._set_layout(hkl)


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value

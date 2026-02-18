"""Global hotkey support using RegisterHotKey."""

import logging
from ctypes import byref
from ctypes.wintypes import MSG
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QThread, pyqtSlot

from core.event_service import EventService
from core.global_state import get_bar_screens
from core.utils.win32.bindings import user32
from core.utils.win32.bindings.kernel32 import GetCurrentThreadId

# Windows message constants
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312

# Modifier flags for RegisterHotKey
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Key name to virtual key code mapping
_KEY_NAME_TO_VK = {
    # Special keys
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    # Arrow keys
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    # Other keys
    "pause": 0x13,
    "capslock": 0x14,
    "caps": 0x14,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    # Numpad keys
    "numpad0": 0x60,
    "numpad1": 0x61,
    "numpad2": 0x62,
    "numpad3": 0x63,
    "numpad4": 0x64,
    "numpad5": 0x65,
    "numpad6": 0x66,
    "numpad7": 0x67,
    "numpad8": 0x68,
    "numpad9": 0x69,
    "multiply": 0x6A,
    "add": 0x6B,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
    # Punctuation and symbols
    "semicolon": 0xBA,
    "equal": 0xBB,
    "equals": 0xBB,
    "comma": 0xBC,
    "minus": 0xBD,
    "period": 0xBE,
    "slash": 0xBF,
    "backquote": 0xC0,
    "grave": 0xC0,
    "bracketleft": 0xDB,
    "backslash": 0xDC,
    "bracketright": 0xDD,
    "quote": 0xDE,
}


@dataclass(frozen=True, slots=True)
class HotkeyBinding:
    """Single hotkey binding configuration."""

    hotkey: str
    widget_name: str
    action: str
    vk: int
    modifiers: int


def parse_hotkey(hotkey: str) -> Optional[tuple[int, int]]:
    """Parse a hotkey string into (modifiers, vk) for RegisterHotKey.

    Args:
        hotkey: Key combination like "win+c", "ctrl+shift+f1"

    Returns:
        (modifiers, vk) tuple or None if invalid.
    """
    if not hotkey or not isinstance(hotkey, str):
        return None

    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return None

    modifiers = 0
    key_name = None

    for part in parts:
        if part in ("win", "windows", "super", "meta"):
            modifiers |= MOD_WIN
        elif part == "alt":
            modifiers |= MOD_ALT
        elif part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part == "shift":
            modifiers |= MOD_SHIFT
        else:
            if key_name is not None:
                logging.warning(f"Invalid hotkey '{hotkey}': multiple non-modifier keys")
                return None
            key_name = part

    if key_name is None:
        logging.warning(f"Invalid hotkey '{hotkey}': no key specified")
        return None

    # Resolve virtual key code
    vk = _KEY_NAME_TO_VK.get(key_name)

    if vk is None:
        # Single character (A-Z, 0-9)
        if len(key_name) == 1:
            char = key_name.upper()
            if char.isalnum():
                vk = ord(char)
        # Function keys F1-F24
        elif key_name.startswith("f") and key_name[1:].isdigit():
            fn = int(key_name[1:])
            if 1 <= fn <= 24:
                vk = 0x70 + (fn - 1)  # VK_F1 = 0x70

    if vk is None:
        logging.warning(f"Invalid hotkey '{hotkey}': unknown key '{key_name}'")
        return None

    return modifiers, vk


class HotkeyDispatcher(QObject):
    """Dispatches hotkey events to widgets via EventService on the main Qt thread."""

    def __init__(self) -> None:
        super().__init__()
        self._event_service = EventService()

    @pyqtSlot(str, str, str)
    def dispatch(self, widget_name: str, action: str, screen_name: str) -> None:
        """Dispatch a hotkey event to the target widget."""
        self._event_service.emit_event("handle_widget_hotkey", widget_name, action, screen_name)


class HotkeyListener(QThread):
    """Background thread that registers global hotkeys via RegisterHotKey."""

    def __init__(self, bindings: list[HotkeyBinding], dispatcher: HotkeyDispatcher) -> None:
        super().__init__()
        self._bindings = bindings
        self._dispatcher = dispatcher
        self._thread_id: int | None = None

        # Map hotkey ID -> binding for WM_HOTKEY dispatch
        self._id_to_binding: dict[int, HotkeyBinding] = {}

    def __str__(self) -> str:
        return "HotkeyListener"

    def _register_hotkeys(self) -> None:
        """Register all hotkey bindings with Windows."""
        for i, binding in enumerate(self._bindings):
            hotkey_id = i + 1  # IDs must be > 0
            mods = binding.modifiers | MOD_NOREPEAT
            if user32.RegisterHotKey(None, hotkey_id, mods, binding.vk):
                self._id_to_binding[hotkey_id] = binding
                logging.debug(f"Registered hotkey {binding.hotkey}")
            else:
                logging.warning(
                    f"Failed to register hotkey {binding.hotkey} - it may be in use by another application."
                )

    def _unregister_hotkeys(self) -> None:
        """Unregister all hotkey bindings."""
        for hotkey_id in self._id_to_binding:
            user32.UnregisterHotKey(None, hotkey_id)
        self._id_to_binding.clear()

    def _emit_binding(self, binding: HotkeyBinding) -> None:
        """Emit a hotkey event to the dispatcher on the main thread."""
        from core.utils.win32.utilities import find_focused_screen

        available_screens = get_bar_screens()
        screen_name = find_focused_screen(follow_mouse=False, follow_window=True, screens=available_screens)

        QMetaObject.invokeMethod(
            self._dispatcher,
            "dispatch",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, binding.widget_name),
            Q_ARG(str, binding.action),
            Q_ARG(str, screen_name or ""),
        )

    def run(self) -> None:
        """Register hotkeys and process WM_HOTKEY messages."""
        self._thread_id = GetCurrentThreadId()

        if not self._bindings:
            return

        # Initialize message queue
        msg = MSG()
        user32.PeekMessageW(byref(msg), None, 0, 0, 0)

        self._register_hotkeys()
        if not self._id_to_binding:
            return

        # Message loop - GetMessageW returns WM_HOTKEY for thread-level hotkeys
        while True:
            result = user32.GetMessageW(byref(msg), None, 0, 0)
            if result == -1:
                logging.error("GetMessageW failed in hotkey listener")
                break
            if result == 0:
                break

            if msg.message == WM_HOTKEY:
                binding = self._id_to_binding.get(msg.wParam)
                if binding:
                    try:
                        self._emit_binding(binding)
                    except Exception:
                        logging.exception("Hotkey dispatch failed")

        self._unregister_hotkeys()

    def stop(self) -> None:
        """Stop the hotkey listener."""
        self._unregister_hotkeys()
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)


def collect_widget_keybindings(widget_name: str, keybindings: list[dict]) -> list[HotkeyBinding]:
    """Parse keybinding configs for a widget into HotkeyBinding objects."""
    bindings = []

    for kb in keybindings:
        keys = kb.get("keys", "")
        action = kb.get("action", "")

        if not keys or not action:
            logging.warning(f"Invalid keybinding for {widget_name}: missing 'keys' or 'action'")
            continue

        parsed = parse_hotkey(keys)
        if parsed is None:
            continue

        modifiers, vk = parsed
        binding = HotkeyBinding(
            hotkey=keys,
            widget_name=widget_name,
            action=action,
            vk=vk,
            modifiers=modifiers,
        )
        bindings.append(binding)

    return bindings

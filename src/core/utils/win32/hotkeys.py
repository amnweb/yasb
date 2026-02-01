"""
Global hotkey support using low-level keyboard hooks.
"""

import ctypes
import logging
from ctypes import byref
from ctypes.wintypes import MSG
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, Qt, QThread, pyqtSlot

from core.event_service import EventService
from core.global_state import get_bar_screens
from core.utils.win32.bindings import user32
from core.utils.win32.bindings.kernel32 import GetCurrentThreadId, GetLastError, GetModuleHandle
from core.utils.win32.bindings.user32 import HOOKPROC
from core.utils.win32.structs import KBDLLHOOKSTRUCT
from core.utils.win32.utilities import find_focused_screen

# Windows message constants
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

# Hook type
WH_KEYBOARD_LL = 13

# Modifier flags
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_LWIN = 0x0010  # Left Win key
MOD_RWIN = 0x0020  # Right Win key

# Virtual key codes for modifiers
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt key
VK_LWIN = 0x5B
VK_RWIN = 0x5C

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


@dataclass(frozen=True)
class HotkeyBinding:
    """Represents a single hotkey binding configuration."""

    hotkey: str  # Original hotkey string (e.g., "win+c")
    widget_name: str  # Widget config name (e.g., "clock", "clock_2")
    action: str  # Callback action name (e.g., "toggle_calendar")
    modifiers: int  # Modifier flags (MOD_ALT, MOD_CONTROL, etc.)
    vk: int  # Virtual key code
    require_lwin: bool = False  # Require specifically left Win key
    require_rwin: bool = False  # Require specifically right Win key


def parse_hotkey(hotkey: str) -> Optional[tuple[int, int, bool, bool]]:
    """
    Parse a hotkey string into modifier flags, virtual key code, and Win key specificity.

    Args:
        hotkey: A hotkey string like "win+c", "ctrl+shift+f1", "lwin+space"

    Returns:
        A tuple of (modifiers, vk, require_lwin, require_rwin) or None if invalid.
        - modifiers: Bitmask of MOD_* flags
        - vk: Virtual key code
        - require_lwin: True if only left Win should trigger
        - require_rwin: True if only right Win should trigger
    """
    if not hotkey or not isinstance(hotkey, str):
        return None

    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return None

    modifiers = 0
    key_name = None
    require_lwin = False
    require_rwin = False

    for part in parts:
        # Left Win key only
        if part in ("lwin", "leftwin", "left_win"):
            modifiers |= MOD_WIN
            require_lwin = True
        # Right Win key only
        elif part in ("rwin", "rightwin", "right_win"):
            modifiers |= MOD_WIN
            require_rwin = True
        # Any Win key
        elif part in ("win", "windows", "super", "meta"):
            modifiers |= MOD_WIN
        elif part in ("alt",):
            modifiers |= MOD_ALT
        elif part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part in ("shift",):
            modifiers |= MOD_SHIFT
        else:
            # This should be the main key
            if key_name is not None:
                # Multiple non-modifier keys specified
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

    return modifiers, vk, require_lwin, require_rwin


class HotkeyDispatcher(QObject):
    """
    Dispatcher that receives hotkey events from the listener thread
    and emits them through the EventService on the main Qt thread.
    """

    def __init__(self) -> None:
        super().__init__()
        self._event_service = EventService()

    @pyqtSlot(str, str, str)
    def dispatch(self, widget_name: str, action: str, bar_id: str) -> None:
        """
        Dispatch a hotkey event to widgets via EventService.

        Args:
            widget_name: The widget config name that should handle this hotkey
            action: The callback action to invoke
            bar_id: The bar_id where the hotkey should be handled
        """
        self._event_service.emit_event("handle_widget_hotkey", widget_name, action, bar_id)


class HotkeyListener(QThread):
    """
    Background thread that installs a low-level keyboard hook
    and listens for configured hotkey combinations.
    """

    def __init__(
        self,
        bindings: list[HotkeyBinding],
        dispatcher: HotkeyDispatcher,
        bar_id_to_screen: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._bindings = bindings
        self._dispatcher = dispatcher
        self._bar_id_to_screen = bar_id_to_screen or {}
        self._thread_id: int | None = None
        self._hook_handle: int | None = None
        self._hook_proc = None

    def __str__(self) -> str:
        return "HotkeyListener"

    def _current_modifiers(self) -> tuple[int, bool, bool]:
        """
        Get the current state of modifier keys.

        Returns:
            A tuple of (modifiers, lwin_pressed, rwin_pressed)
        """
        modifiers = 0
        if user32.GetKeyState(VK_SHIFT) & 0x8000:
            modifiers |= MOD_SHIFT
        if user32.GetKeyState(VK_CONTROL) & 0x8000:
            modifiers |= MOD_CONTROL
        if user32.GetKeyState(VK_MENU) & 0x8000:
            modifiers |= MOD_ALT

        lwin_pressed = bool(user32.GetKeyState(VK_LWIN) & 0x8000)
        rwin_pressed = bool(user32.GetKeyState(VK_RWIN) & 0x8000)

        if lwin_pressed or rwin_pressed:
            modifiers |= MOD_WIN

        return modifiers, lwin_pressed, rwin_pressed

    def _match_binding(self, vk_code: int) -> HotkeyBinding | None:
        """
        Find a matching binding for the given virtual key code and current modifiers.

        Args:
            vk_code: The virtual key code that was pressed

        Returns:
            The matching HotkeyBinding or None
        """
        current_mods, lwin_pressed, rwin_pressed = self._current_modifiers()

        for binding in self._bindings:
            # Check if the main key matches
            if binding.vk != vk_code:
                continue

            # Check modifier flags (excluding win-specific flags)
            required_mods = binding.modifiers & (MOD_SHIFT | MOD_CONTROL | MOD_ALT | MOD_WIN)
            if current_mods != required_mods:
                continue

            # Check Win key specificity
            if binding.require_lwin:
                # Only left Win should be pressed
                if not lwin_pressed or rwin_pressed:
                    continue
            elif binding.require_rwin:
                # Only right Win should be pressed
                if not rwin_pressed or lwin_pressed:
                    continue

            return binding

        return None

    def _install_hook(self) -> None:
        """Install the low-level keyboard hook."""

        def _hook_callback(n_code: int, w_param: int, l_param: int) -> int:
            # Only process if code is 0 (HC_ACTION) and it's a key down event
            if n_code == 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kbd = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk_code = int(kbd.vkCode)

                binding = self._match_binding(vk_code)
                if binding:
                    try:
                        self._emit_binding(binding)
                    except Exception:
                        logging.exception("Hotkey dispatch failed")
                    # Return 1 to block the key event from other applications
                    return 1

            return user32.CallNextHookEx(self._hook_handle or 0, n_code, w_param, l_param)

        # Create the callback with the correct signature
        self._hook_proc = HOOKPROC(_hook_callback)
        module_handle = GetModuleHandle(None)
        self._hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, module_handle, 0)

        if not self._hook_handle:
            error = GetLastError()
            logging.error(f"Failed to install keyboard hook. Win32 error: {error}")

    def _emit_binding(self, binding: HotkeyBinding) -> None:
        """Emit a hotkey event to the dispatcher on the main thread."""
        available_screens = get_bar_screens()
        screen_name = find_focused_screen(follow_mouse=False, follow_window=True, screens=available_screens)

        # Find the bar_id on the focused screen
        target_bar_id = ""
        if screen_name:
            for bar_id, bar_screen in self._bar_id_to_screen.items():
                if bar_screen == screen_name:
                    target_bar_id = bar_id
                    break

        QMetaObject.invokeMethod(
            self._dispatcher,
            "dispatch",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, binding.widget_name),
            Q_ARG(str, binding.action),
            Q_ARG(str, target_bar_id),
        )

    def run(self) -> None:
        """Main thread loop - installs hook and processes messages."""
        self._thread_id = GetCurrentThreadId()

        if not self._bindings:
            return

        # Initialize message queue
        msg = MSG()
        user32.PeekMessageW(byref(msg), None, 0, 0, 0)

        # Install the hook
        self._install_hook()
        if not self._hook_handle:
            return

        # Message loop
        while True:
            result = user32.GetMessageW(byref(msg), None, 0, 0)
            if result == -1:
                logging.error("GetMessageW failed in hotkey listener")
                break
            if result == 0:
                # WM_QUIT received
                break

    def stop(self) -> None:
        """Stop the hotkey listener and clean up resources."""
        if self._hook_handle:
            try:
                user32.UnhookWindowsHookEx(self._hook_handle)
            except Exception:
                pass
            self._hook_handle = None

        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)


def collect_widget_keybindings(widget_name: str, keybindings: list[dict]) -> list[HotkeyBinding]:
    """
    Parse keybindings configuration for a widget and return HotkeyBinding objects.

    Args:
        widget_name: The widget config name (e.g., "clock", "clock_2")
        keybindings: List of keybinding dicts with 'keys' and 'action' fields

    Returns:
        List of valid HotkeyBinding objects
    """
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

        modifiers, vk, require_lwin, require_rwin = parsed
        binding = HotkeyBinding(
            hotkey=keys,
            widget_name=widget_name,
            action=action,
            modifiers=modifiers,
            vk=vk,
            require_lwin=require_lwin,
            require_rwin=require_rwin,
        )
        bindings.append(binding)

    return bindings

"""Runtime hotkey support for the monitor profile widget.

The bar-level hotkey system only registers bindings from static widget config
at bar initialization. Profiles and monitor toggles are dynamic (created after
startup, or not known until runtime), so this module manages its own
RegisterHotKey bindings on a background thread and dispatches them through the
same "handle_widget_hotkey" EventService channel the base widget listens to.
"""

import logging
import threading
from dataclasses import dataclass

from core.events.service import EventService
from core.utils.win32.bindings import user32
from core.utils.win32.bindings.kernel32 import GetCurrentThreadId
from core.utils.win32.hotkeys import MOD_NOREPEAT

logger = logging.getLogger("monitor_profile_hotkeys")

WM_QUIT = 0x0012
WM_HOTKEY = 0x0312


@dataclass(frozen=True, slots=True)
class _RuntimeBinding:
    action: str
    vk: int
    modifiers: int


class RuntimeHotkeyManager:
    """Registers global hotkeys at runtime and dispatches them as widget hotkey events."""

    _instance: RuntimeHotkeyManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._bindings: dict[int, _RuntimeBinding] = {}
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    @classmethod
    def instance(cls) -> RuntimeHotkeyManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = RuntimeHotkeyManager()
        return cls._instance

    def set_bindings(self, bindings: dict[str, tuple[str, int, int]]) -> None:
        """Replace all bindings. Keys are arbitrary ids, values are (action, vk, modifiers)."""
        self._bindings = {hid: _RuntimeBinding(action, vk, mods) for hid, (action, vk, mods) in bindings.items()}
        self._restart()

    def stop(self) -> None:
        self._bindings = {}
        self._stop_thread()

    # ------------------------------------------------------------------ thread

    def _restart(self) -> None:
        self._stop_thread()
        if not self._bindings:
            return
        self._thread = threading.Thread(target=self._run, name="MonitorProfileHotkeys", daemon=True)
        self._thread.start()

    def _stop_thread(self) -> None:
        thread_id = self._thread_id
        if thread_id is not None:
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._thread_id = None

    def _run(self) -> None:
        import ctypes
        from ctypes.wintypes import MSG

        self._thread_id = GetCurrentThreadId()
        id_to_binding: dict[int, _RuntimeBinding] = {}
        for i, binding in enumerate(self._bindings.values()):
            hotkey_id = 0xB000 + i  # Avoid clashing with the bar manager's ids (1..N)
            if user32.RegisterHotKey(None, hotkey_id, binding.modifiers | MOD_NOREPEAT, binding.vk):
                id_to_binding[hotkey_id] = binding
            else:
                logger.warning(
                    "Failed to register runtime hotkey for action '%s' - it may be in use by another application.",
                    binding.action,
                )
        if not id_to_binding:
            return

        msg = MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == -1 or result == 0:
                break
            if msg.message == WM_HOTKEY:
                binding = id_to_binding.get(msg.wParam)
                if binding:
                    self._dispatch(binding)

    def _dispatch(self, binding: _RuntimeBinding) -> None:
        """Emit the action through the widget hotkey event channel.

        Resolves the first live widget instance; dead instances (from a
        previous bar build before a config reload) are purged first because
        calling into them raises RuntimeError.
        """
        widget = self._resolve_widget()
        if widget is None:
            return
        screen_name = widget.screen_name or ""
        EventService().emit_event("handle_widget_hotkey", widget.widget_name, binding.action, screen_name)

    @staticmethod
    def _resolve_widget():
        """Find the first live MonitorProfileWidget instance, purging dead ones."""
        from core.utils.qobject import is_valid_qobject
        from core.widgets.yasb.monitor_profile import MonitorProfileWidget

        instances = MonitorProfileWidget.instances()
        for widget in instances:
            if is_valid_qobject(widget) and widget.widget_name:
                return widget
        # All instances are dead (e.g. during/after a config reload) - drop them
        MonitorProfileWidget._instances.clear()
        return None

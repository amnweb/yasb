import logging
from collections.abc import Callable
from contextlib import suppress

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtBoundSignal, pyqtSignal

from core.events.win32 import WinEvent
from core.services.taskbar.application_window import ApplicationWindow
from core.utils.win32 import constants as WCONST
from core.utils.win32.bindings.ole32 import ole32
from core.utils.win32.bindings.user32 import (
    EnumWindows,
    GetForegroundWindow,
    IsWindow,
)
from core.utils.win32.bindings.user32 import user32 as _user32_raw
from core.utils.win32.event_listener import win_event
from core.utils.win32.shell_hook import shell_event
from core.utils.win32.structs import WNDENUMPROC

logger = logging.getLogger("taskbar_window_manager")
logger.setLevel(logging.INFO)
# The WinEvents the manager follows, from the shared hook in core.utils.win32.event_listener
WIN_EVENTS = (
    WinEvent.EventObjectCloaked,
    WinEvent.EventObjectUncloaked,
    WinEvent.EventObjectShow,
    WinEvent.EventObjectHide,
    WinEvent.EventSystemMinimizeStart,
    WinEvent.EventSystemMinimizeEnd,
)
# Global shared instance
_shared_task_manager: TaskbarWindowManager | None = None


def get_shared_task_manager() -> TaskbarWindowManager:
    """Return the singleton TaskbarWindowManager instance, creating it if needed."""
    global _shared_task_manager
    if _shared_task_manager is None:
        _shared_task_manager = TaskbarWindowManager()
    return _shared_task_manager


def start_shared_task_manager() -> TaskbarWindowManager:
    """Start the shared manager, once.

    Cloaked windows, such as those on other virtual desktops, are kept; each widget leaves them out if it wants.
    """
    task_manager = get_shared_task_manager()
    if task_manager.is_initialized():
        return task_manager
    app = QCoreApplication.instance()
    task_manager.keep_cloaked_tasks = True
    task_manager.start()
    if app is not None:
        # Its shell and event hooks are taken down with YASB, as the taskbar widget did
        app.aboutToQuit.connect(task_manager.stop)
    return task_manager


class TaskbarWindowManager(QObject):
    """
    Tracks top-level windows and emits signals on create/destroy/update/activation.
    Gets the shell's messages from core.utils.win32.shell_hook and WinEvents from core.utils.win32.event_listener.
    """

    # Signal definitions for Qt integration
    window_added = pyqtSignal(int, dict)
    window_removed = pyqtSignal(int, dict)
    window_updated = pyqtSignal(int, dict)
    window_monitor_changed = pyqtSignal(int, dict)
    window_minimize_changed = pyqtSignal(int, bool)

    def __init__(self):
        super().__init__()
        self._windows: dict[int, ApplicationWindow] = {}
        self._initialized = False
        # What start connected, so stop disconnects without asking the shared hooks again
        self._shell_connections: list[tuple[pyqtBoundSignal, Callable[[int], object]]] = []
        self._win_signals: list[pyqtBoundSignal] = []
        self._com_initialized = False
        self.keep_cloaked_tasks = False
        # Debounce timers for per-hwnd coalesced updates (e.g., Explorer icon settling)
        self._pending_updates: dict[int, QTimer] = {}

        # Windows API setup
        self._user32 = _user32_raw
        self._ole32 = ole32

        # COM initialization
        try:
            self._ole32.CoInitialize(0)
            self._com_initialized = True
        except Exception as e:
            logger.warning("CoInitialize failed or already initialized: %s", e)

    def start(self):
        """Follow the shell's messages and WinEvents, and enumerate existing windows."""
        if self._initialized:
            return

        try:
            self._connect_shell_messages()
            self._connect_win_events()

            # Enumerate existing windows
            self._enumerate_existing_windows()

            self._initialized = True
            logger.info("TaskbarWindowManager is starting...")

        except Exception as e:
            logger.error("Failed to start TaskbarWindowManager: %s", e)
            self.stop()
            raise

    def stop(self):
        """Tear down hooks. Balance COM init if we created it."""
        if not self._initialized:
            return

        try:
            # Cleanup any pending debounce timers
            try:
                for t in list(self._pending_updates.values()):
                    try:
                        t.stop()
                        t.deleteLater()
                    except Exception:
                        pass
            finally:
                self._pending_updates.clear()
            self._disconnect_win_events()
            self._disconnect_shell_messages()

            self._initialized = False
            logger.info("TaskbarWindowManager stopped")

        except Exception as e:
            logger.error("Error stopping TaskbarWindowManager: %s", e)

        # COM uninitialization (balance CoInitialize)
        try:
            if self._com_initialized:
                self._ole32.CoUninitialize()
                self._com_initialized = False
        except Exception as e:
            logger.warning("CoUninitialize failed: %s", e)

    def _connect_shell_messages(self) -> None:
        handlers = {
            WCONST.HSHELL_WINDOWCREATED: self._on_window_created,
            WCONST.HSHELL_WINDOWDESTROYED: self._on_window_destroyed,
            WCONST.HSHELL_ENDTASK: self._on_window_destroyed,
            WCONST.HSHELL_WINDOWACTIVATED: self._on_window_activated,
            WCONST.HSHELL_RUDEAPPACTIVATED: self._on_window_activated,
            WCONST.HSHELL_REDRAW: self._on_window_redraw,
            WCONST.HSHELL_FLASH: self._on_window_flash,
            WCONST.HSHELL_WINDOWREPLACING: self._on_window_replacing,
            WCONST.HSHELL_WINDOWREPLACED: self._on_window_replaced,
            WCONST.HSHELL_MONITORCHANGED: self._on_window_monitor_changed,
        }
        for code, handler in handlers.items():
            signal = shell_event(code)
            signal.connect(handler)
            self._shell_connections.append((signal, handler))

    def _disconnect_shell_messages(self) -> None:
        for signal, handler in self._shell_connections:
            with suppress(TypeError):
                signal.disconnect(handler)
        self._shell_connections.clear()

    def _connect_win_events(self) -> None:
        for event in WIN_EVENTS:
            signal = win_event(event)
            signal.connect(self._on_win_event)
            self._win_signals.append(signal)

    def _disconnect_win_events(self) -> None:
        for signal in self._win_signals:
            with suppress(TypeError):
                signal.disconnect(self._on_win_event)
        self._win_signals.clear()

    def _on_win_event(self, hwnd: int, event: WinEvent) -> None:
        """A window was cloaked, shown, hidden or minimized; each is looked at after a short wait."""
        if event == WinEvent.EventObjectUncloaked:
            QTimer.singleShot(100, lambda: self._on_window_uncloaked(hwnd))
        elif event == WinEvent.EventObjectCloaked:
            QTimer.singleShot(50, lambda: self._on_window_cloaked(hwnd))
        elif event == WinEvent.EventObjectShow:
            QTimer.singleShot(0, lambda: self._on_window_show(hwnd))
        elif event == WinEvent.EventObjectHide:
            QTimer.singleShot(0, lambda: self._on_window_hide(hwnd))
        elif event == WinEvent.EventSystemMinimizeStart:
            QTimer.singleShot(0, lambda: self._on_window_minimized(hwnd, True))
        elif event == WinEvent.EventSystemMinimizeEnd:
            QTimer.singleShot(0, lambda: self._on_window_minimized(hwnd, False))

    def _on_window_created(self, hwnd: int) -> None:
        """Create or update immediately; rely on HSHELL_MONITORCHANGED for monitor updates."""
        try:
            if hwnd in self._windows:
                self._update_window(hwnd)
            else:
                self._add_window(hwnd)
        except Exception as e:
            logger.error("Error handling window created for %s: %s", hwnd, e)

    def _on_window_destroyed(self, hwnd: int) -> None:
        """Remove a window when it's destroyed."""
        try:
            if hwnd in self._windows:
                self._remove_window(hwnd)
        except Exception as e:
            logger.error("Error handling window destroyed for %s: %s", hwnd, e)

    def _on_window_minimized(self, hwnd: int, minimized: bool) -> None:
        """Report that a tracked window was minimized or restored."""
        if hwnd in self._windows:
            self.window_minimize_changed.emit(hwnd, minimized)

    def _on_window_activated(self, hwnd: int) -> None:
        """Mark activated window active and clear flashing; emit updates for state changes."""
        try:
            foreground_hwnd = GetForegroundWindow()

            if not hwnd and foreground_hwnd:
                hwnd = foreground_hwnd

            windows_to_update: set[int] = set()
            old_states: dict[int, bool] = {}

            for window_hwnd, window in self._windows.items():
                if hasattr(window, "is_active"):
                    old_states[window_hwnd] = window.is_active

            for window_hwnd, window in self._windows.items():
                if hasattr(window, "is_active"):
                    window.is_active = False
                    if old_states.get(window_hwnd, False) != window.is_active:
                        windows_to_update.add(window_hwnd)

            if hwnd and hwnd in self._windows:
                window = self._windows[hwnd]
                if hasattr(window, "is_active"):
                    window.is_active = True
                    if old_states.get(hwnd, False) != window.is_active:
                        windows_to_update.add(hwnd)
                if hasattr(window, "is_flashing") and window.is_flashing:
                    window.is_flashing = False
                    windows_to_update.add(hwnd)
            elif hwnd:
                self._add_window(hwnd, is_active=True)
            else:
                if foreground_hwnd and foreground_hwnd in self._windows:
                    window = self._windows[foreground_hwnd]
                    if hasattr(window, "is_active"):
                        window.is_active = True
                        if old_states.get(foreground_hwnd, False) != window.is_active:
                            windows_to_update.add(foreground_hwnd)
                    if hasattr(window, "is_flashing") and window.is_flashing:
                        window.is_flashing = False
                        windows_to_update.add(foreground_hwnd)

            for window_hwnd in windows_to_update:
                if window_hwnd in self._windows:
                    window_data = self._windows[window_hwnd].as_dict()
                    self.window_updated.emit(window_hwnd, window_data)

        except Exception as e:
            logger.error("Error handling window activated for %s: %s", hwnd, e)

    def _on_window_redraw(self, hwnd: int) -> None:
        """Update or add window on redraw notification."""
        try:
            if hwnd in self._windows:
                # Debounce redraw to avoid reading icon too early (e.g., Explorer folder switch)
                self._debounce_update(hwnd, delay=50)
            else:
                self._add_window(hwnd)
        except Exception as e:
            logger.error("Error handling window redraw for %s: %s", hwnd, e)

    def _on_window_flash(self, hwnd: int) -> None:
        """Mark window as flashing and emit an update when the state changes."""
        try:
            if hwnd in self._windows:
                window = self._windows[hwnd]
                if hasattr(window, "is_flashing"):
                    was_flashing = window.is_flashing
                    window.is_flashing = True
                    if not was_flashing:
                        window_data = window.as_dict()
                        self.window_updated.emit(hwnd, window_data)
                    else:
                        self._update_window(hwnd)
                else:
                    self._update_window(hwnd)
            else:
                self._add_window(hwnd, is_flashing=True)
        except Exception as e:
            logger.error("Error handling window flash for %s: %s", hwnd, e)

    def _on_window_replacing(self, hwnd: int) -> None:
        """Handle replacement by updating if present."""
        if hwnd in self._windows:
            self._update_window(hwnd)

    def _on_window_replaced(self, hwnd: int) -> None:
        """Remove old window on replacement."""
        if hwnd in self._windows:
            self._remove_window(hwnd)

    def _on_window_monitor_changed(self, hwnd: int) -> None:
        """Emit monitor change and update if other properties changed."""
        try:
            if hwnd in self._windows:
                app_window = self._windows[hwnd]
                old_data = app_window.as_dict()

                app_window.update()
                new_data = app_window.as_dict()

                self.window_monitor_changed.emit(hwnd, new_data)

                if old_data != new_data:
                    self.window_updated.emit(hwnd, new_data)

            else:
                self._try_add_window_delayed(hwnd, delay=50)
        except Exception as e:
            logger.error("Error handling monitor change for %s: %s", hwnd, e)

    def _on_window_cloaked(self, hwnd: int) -> None:
        """Cloaked: keep or remove based on preference (keep_cloaked_tasks)."""
        try:
            if hwnd in self._windows:
                app_window = self._windows[hwnd]
                if getattr(self, "keep_cloaked_tasks", False):
                    # Keep and refresh so widgets can react
                    app_window.update()
                    self.window_updated.emit(hwnd, app_window.as_dict())
                else:
                    # Keep UWP transient frames, let widgets filter them
                    is_uwp = False
                    try:
                        cls = (app_window.class_name or "").strip()
                        pname = (app_window.process_name or "").strip()
                        is_uwp = (
                            cls in ("Windows.UI.Core.CoreWindow", "ApplicationFrameWindow")
                            or pname == "ApplicationFrameHost.exe"
                        )
                    except Exception:
                        is_uwp = False

                    if is_uwp:
                        # Keep and refresh _update_window has the UWP transient-keep heuristic
                        app_window.update()
                        self.window_updated.emit(hwnd, app_window.as_dict())
                    else:
                        # Remove when not keeping cloaked tasks
                        self._remove_window(hwnd)
        except Exception as e:
            logger.error("Error handling window cloaked for %s: %s", hwnd, e)

    def _on_window_uncloaked(self, hwnd: int) -> None:
        """Uncloaked: ensure tracking and refresh UI."""
        try:
            if hwnd in self._windows:
                # Already tracked force-emit so widgets that removed it while cloaked can re-add it
                app_window = self._windows[hwnd]
                app_window.update()
                self.window_updated.emit(hwnd, app_window.as_dict())
            else:
                # Was removed while cloaked; add it back now that it's visible
                self._add_window(hwnd)
        except Exception as e:
            logger.error("Error handling window uncloaked for %s: %s", hwnd, e)

    def _on_window_show(self, hwnd: int) -> None:
        """SHOW event add or refresh the window."""
        try:
            if hwnd in self._windows:
                self._update_window(hwnd)
            else:
                self._add_window(hwnd)
        except Exception as e:
            logger.error("Error handling window show for %s: %s", hwnd, e)

    def _on_window_hide(self, hwnd: int) -> None:
        """HIDE event remove from taskbar tracking."""
        try:
            if hwnd in self._windows:
                self._remove_window(hwnd)
        except Exception as e:
            logger.error("Error handling window hide for %s: %s", hwnd, e)

    def _add_window(self, hwnd: int, is_active: bool = False, is_flashing: bool = False) -> None:
        """Create and track a window if it should be on the taskbar."""
        try:
            # Validate the handle is a real window
            if not IsWindow(hwnd):
                return

            # Create ApplicationWindow instance
            app_window = ApplicationWindow(hwnd)

            # Check if window should be shown in taskbar
            if not app_window.is_taskbar_window():
                # For UWP apps, sometimes they need a moment to fully initialize
                # Schedule a delayed check for UWP apps that might not be ready yet
                try:
                    if app_window.class_name in ["ApplicationFrameWindow", "Windows.UI.Core.CoreWindow"]:
                        QTimer.singleShot(500, lambda: self._delayed_uwp_check(hwnd))
                except:
                    pass
                return

            # Set initial state
            if hasattr(app_window, "is_active"):
                app_window.is_active = is_active
            if hasattr(app_window, "is_flashing"):
                app_window.is_flashing = is_flashing

            # Add to collection
            self._windows[hwnd] = app_window

            # Emit signal
            window_data = app_window.as_dict()
            self.window_added.emit(hwnd, window_data)

        except Exception as e:
            logger.error("Error adding window %s: %s", hwnd, e)

    def _delayed_uwp_check(self, hwnd: int) -> None:
        """Retry adding UWP windows after a short delay."""
        try:
            if hwnd in self._windows:
                return

            if not IsWindow(hwnd):
                return

            app_window = ApplicationWindow(hwnd)
            if app_window.is_taskbar_window():
                self._windows[hwnd] = app_window
                window_data = app_window.as_dict()
                self.window_added.emit(hwnd, window_data)
        except Exception as e:
            logger.error("Delayed UWP check failed for %s: %s", hwnd, e)

    def _try_add_window_delayed(self, hwnd: int, delay: int = 50) -> None:
        """Try to add a window after a delay (for monitor changes)."""

        def delayed_check():
            try:
                if hwnd in self._windows:
                    return

                if not IsWindow(hwnd):
                    return

                app_window = ApplicationWindow(hwnd)
                if app_window.is_taskbar_window():
                    self._windows[hwnd] = app_window
                    window_data = app_window.as_dict()
                    self.window_added.emit(hwnd, window_data)
            except Exception as e:
                logger.error("Delayed window add failed for %s: %s", hwnd, e)

        QTimer.singleShot(delay, delayed_check)

    def _remove_window(self, hwnd: int) -> None:
        """Stop tracking a window and emit removal."""
        try:
            if hwnd in self._windows:
                app_window = self._windows[hwnd]
                window_data = app_window.as_dict()
                del self._windows[hwnd]
                self.window_removed.emit(hwnd, window_data)

        except Exception as e:
            logger.error("Error removing window %s: %s", hwnd, e)

    def _update_window(self, hwnd: int) -> None:
        """Update cached data for a window and emit if something changed."""
        try:
            if hwnd in self._windows:
                app_window = self._windows[hwnd]
                old_data = app_window.as_dict()

                app_window.update()

                if not app_window.is_taskbar_window():
                    # Keep UWP windows through transient transitions, let widgets filter them
                    try:
                        cls = (app_window.class_name or "").strip()
                        pname = (app_window.process_name or "").strip()
                        is_uwp = (
                            cls in ("Windows.UI.Core.CoreWindow", "ApplicationFrameWindow")
                            or pname == "ApplicationFrameHost.exe"
                        )
                        if is_uwp:
                            new_data = app_window.as_dict()
                            self.window_updated.emit(hwnd, new_data)
                            return
                    except Exception:
                        pass
                    # If cloaked and preference says keep cloaked tasks, keep and emit
                    try:
                        is_cloaked = bool(app_window.is_cloaked())
                    except Exception:
                        is_cloaked = False

                    if is_cloaked and getattr(self, "keep_cloaked_tasks", False):
                        new_data = app_window.as_dict()
                        self.window_updated.emit(hwnd, new_data)
                        return

                    # Otherwise remove
                    self._remove_window(hwnd)
                    return

                new_data = app_window.as_dict()

                if old_data != new_data:
                    self.window_updated.emit(hwnd, new_data)

        except Exception as e:
            logger.error("Error updating window %s: %s", hwnd, e)

    def _schedule_window_update(self, hwnd: int) -> None:
        """Schedule a window update on the Qt event loop."""
        QTimer.singleShot(0, lambda: self._update_window(hwnd))

    def _debounce_update(self, hwnd: int, delay: int = 60):
        """Coalesce rapid updates for a hwnd within 'delay' ms by resetting a single-shot timer."""
        try:
            existing = self._pending_updates.get(hwnd)
            if existing is not None:
                try:
                    existing.stop()
                    existing.deleteLater()
                except Exception:
                    pass
            timer = QTimer(self)
            timer.setSingleShot(True)

            def fire():
                try:
                    self._pending_updates.pop(hwnd, None)
                except Exception:
                    self._pending_updates.clear()
                self._update_window(hwnd)

            timer.timeout.connect(fire)
            self._pending_updates[hwnd] = timer
            timer.start(max(0, int(delay)))
        except Exception as e:
            logger.debug("debounce failed for %s: %s", hwnd, e)

    def _enumerate_existing_windows(self):
        """Enumerate and track existing windows at startup."""
        try:

            def enum_proc(hwnd: int, lParam: object) -> bool:
                try:
                    self._add_window(hwnd)
                except:
                    pass
                return True

            EnumWindows(WNDENUMPROC(enum_proc), 0)

            foreground_hwnd = GetForegroundWindow()
            if foreground_hwnd and foreground_hwnd in self._windows:
                window = self._windows[foreground_hwnd]
                if hasattr(window, "is_active"):
                    window.is_active = True

        except Exception as e:
            logger.error("Error enumerating existing windows: %s", e)

    # Removed helper: simplified to call _on_window_monitor_changed after creation

    # Hidden window creation/destruction removed

    def rescan_windows(self) -> None:
        """Forget every tracked window and enumerate the open ones again."""
        self._windows.clear()
        self._enumerate_existing_windows()

    def get_windows(self) -> dict[int, ApplicationWindow]:
        """Return a copy of all tracked windows keyed by hwnd."""
        return self._windows.copy()

    def get_window(self, hwnd: int) -> ApplicationWindow | None:
        """Return a tracked window by handle or None."""
        return self._windows.get(hwnd)

    def is_initialized(self) -> bool:
        """True if the manager has started and installed its hooks."""
        return self._initialized

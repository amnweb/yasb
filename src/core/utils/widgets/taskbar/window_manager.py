import ctypes
import logging
from ctypes import wintypes
from typing import Dict, Optional

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, QTimer, pyqtSignal

from core.utils.widgets.taskbar.application_window import ApplicationWindow

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Global shared instance
_shared_task_manager = None
_shellhook_event_filter = None


def get_shared_task_manager(excluded_classes=None, ignored_processes=None, ignored_titles=None):
    """Return the singleton TaskbarWindowManager instance, creating it if needed."""
    global _shared_task_manager
    if _shared_task_manager is None:
        _shared_task_manager = TaskbarWindowManager(excluded_classes, ignored_processes, ignored_titles)
    return _shared_task_manager


def connect_taskbar(widget):
    """Wire a taskbar widget to the shared manager and push current windows to it."""
    # Get exclusion lists from the widget
    excluded_classes = set()
    ignored_processes = set()
    ignored_titles = set()

    if hasattr(widget, "_ignore_apps"):
        excluded_classes.update(widget._ignore_apps.get("classes", []))
        ignored_processes.update(widget._ignore_apps.get("processes", []))
        ignored_titles.update(widget._ignore_apps.get("titles", []))

    task_manager = get_shared_task_manager(excluded_classes, ignored_processes, ignored_titles)

    # Connect signals
    task_manager.window_added.connect(widget._on_window_added)
    task_manager.window_removed.connect(widget._on_window_removed)
    task_manager.window_updated.connect(widget._on_window_updated)
    task_manager.window_monitor_changed.connect(widget._on_window_monitor_changed)

    # Install native event filter once to catch SHELLHOOK via Qt
    global _shellhook_event_filter
    try:
        if _shellhook_event_filter is None and QCoreApplication.instance() is not None:
            _shellhook_event_filter = _ShellHookEventFilter(lambda: _shared_task_manager)
            QCoreApplication.instance().installNativeEventFilter(_shellhook_event_filter)
    except Exception as e:
        logger.warning(f"Failed to install native event filter: {e}")

    # Try to obtain the top-level Qt window handle
    hwnd = None
    try:
        top = widget.window() if hasattr(widget, "window") else None
        if top is not None and hasattr(top, "winId"):
            hwnd = int(top.winId())
    except Exception as e:
        logger.warning(f"Unable to obtain Qt window handle for shell hook: {e}")

    # Start the task manager using the Qt hwnd
    task_manager.start(hwnd)

    # Send existing windows to this widget
    for hwnd, app_window in task_manager._windows.items():
        try:
            window_data = app_window.as_dict()
            widget._on_window_added(hwnd, window_data)
        except Exception as e:
            logger.error(f"Error sending existing window {hwnd} to widget: {e}")

    return task_manager


class _ShellHookEventFilter(QAbstractNativeEventFilter):
    """Qt native event filter that forwards SHELLHOOK messages to the manager."""

    def __init__(self, manager_getter):
        super().__init__()
        self._get_manager = manager_getter  # callable returning TaskbarWindowManager

    def nativeEventFilter(self, eventType, message):
        # On Windows + PyQt6, eventType is 'windows_generic_MSG' and message is MSG*
        try:
            if eventType != "windows_generic_MSG":
                return False, 0

            import ctypes
            from ctypes import wintypes

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD),
                    ("pt_x", wintypes.LONG),
                    ("pt_y", wintypes.LONG),
                ]

            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
            manager = self._get_manager()
            if not manager or manager.WM_SHELLHOOKMESSAGE is None:
                return False, 0

            if msg.message == manager.WM_SHELLHOOKMESSAGE:
                # Forward to the manager's handler
                manager._handle_shell_hook_message(int(msg.wParam), int(msg.lParam))
                return True, 0

        except Exception:
            pass
        return False, 0


class TaskbarWindowManager(QObject):
    """
    Tracks top-level windows and emits signals on create/destroy/update/activation.
    Receives SHELLHOOK via the application's Qt top-level window; uses WinEvent hooks for cloak changes.
    """

    # Signal definitions for Qt integration
    window_added = pyqtSignal(int, dict)
    window_removed = pyqtSignal(int, dict)
    window_updated = pyqtSignal(int, dict)
    window_monitor_changed = pyqtSignal(int, dict)

    # Windows constants (subset)
    WM_SHELLHOOKMESSAGE = None

    HSHELL_WINDOWCREATED = 1
    HSHELL_WINDOWDESTROYED = 2
    HSHELL_WINDOWACTIVATED = 4
    HSHELL_REDRAW = 6
    HSHELL_ENDTASK = 10
    HSHELL_WINDOWREPLACED = 13
    HSHELL_WINDOWREPLACING = 14
    HSHELL_RUDEAPPACTIVATED = 32772
    HSHELL_FLASH = 32774

    # WinEvent constants for cloak detection
    EVENT_OBJECT_CLOAKED = 0x8017
    EVENT_OBJECT_UNCLOAKED = 0x8018
    WINEVENT_OUTOFCONTEXT = 0x0000
    WINEVENT_SKIPOWNPROCESS = 0x0002

    def __init__(self, excluded_classes=None, ignored_processes=None, ignored_titles=None):
        super().__init__()
        self._windows = {}
        self._initialized = False
        self._shell_hook_registered = False
        self._shell_hook_hwnd = None
        self._win_event_hooks = []
        self._com_initialized = False
        # Debounce timers for per-hwnd coalesced updates (e.g., Explorer icon settling)
        self._pending_updates = {}

        # Store exclusion lists for creating ApplicationWindow instances
        self._excluded_classes = excluded_classes or set()
        self._ignored_processes = ignored_processes or set()
        self._ignored_titles = ignored_titles or set()

        # Windows API setup
        self._user32 = ctypes.windll.user32
        self._ole32 = ctypes.windll.ole32

        # Setup API function signatures
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetForegroundWindow.argtypes = []

        # COM initialization
        try:
            self._ole32.CoInitialize(0)
            self._com_initialized = True
        except Exception as e:
            logger.warning(f"CoInitialize failed or already initialized: {e}")

    def start(self, hwnd: Optional[int] = None):
        """Register shell hooks on provided Qt hwnd; set WinEvent hooks and enumerate existing windows."""
        if self._initialized:
            return

        try:
            if not hwnd:
                raise RuntimeError("Qt top-level window handle (hwnd) is required for shell hooks")
            self._register_shell_hooks(hwnd)
            self._set_win_event_hooks()

            # Enumerate existing windows
            self._enumerate_existing_windows()

            self._initialized = True
            logger.info("TaskbarWindowManager is starting...")

        except Exception as e:
            logger.error(f"Failed to start TaskbarWindowManager: {e}")
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
            self._cleanup_win_event_hooks()
            self._unregister_shell_hooks()

            self._initialized = False
            logger.info("TaskbarWindowManager stopped")

        except Exception as e:
            logger.error(f"Error stopping TaskbarWindowManager: {e}")

        # COM uninitialization (balance CoInitialize)
        try:
            if self._com_initialized:
                self._ole32.CoUninitialize()
                self._com_initialized = False
        except Exception as e:
            logger.warning(f"CoUninitialize failed: {e}")

    def _register_shell_hooks(self, hwnd: int):
        """Register shell hook messages on an existing Qt top-level window handle."""
        try:
            if not hwnd:
                raise ValueError("Invalid hwnd for shell hook registration")

            if not self._user32.RegisterShellHookWindow(hwnd):
                raise RuntimeError("Failed to register shell hook on provided hwnd")

            self.WM_SHELLHOOKMESSAGE = self._user32.RegisterWindowMessageW("SHELLHOOK")
            if not self.WM_SHELLHOOKMESSAGE:
                raise RuntimeError("Failed to register SHELLHOOK message")

            self._shell_hook_registered = True
            self._shell_hook_hwnd = int(hwnd)

        except Exception as e:
            logger.error(f"Failed to register shell hooks on hwnd {hwnd}: {e}")
            raise

    def _set_win_event_hooks(self):
        """Install WinEvent hooks for cloak/uncloak notifications."""
        try:
            WinEventProcType = ctypes.WINFUNCTYPE(
                None,
                ctypes.wintypes.HANDLE,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.HWND,
                ctypes.wintypes.LONG,
                ctypes.wintypes.LONG,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
            )

            def cloak_event_callback(hWinEventHook, eventType, hWnd, idObject, idChild, dwEventThread, dwmsEventTime):
                try:
                    if hWnd and idObject == 0 and idChild == 0:
                        hwnd_int = int(hWnd)

                        if eventType == self.EVENT_OBJECT_UNCLOAKED:
                            QTimer.singleShot(100, lambda: self._on_window_uncloaked(hwnd_int))
                        elif eventType == self.EVENT_OBJECT_CLOAKED:
                            QTimer.singleShot(50, lambda: self._on_window_cloaked(hwnd_int))
                        else:
                            if hwnd_int in self._windows:
                                self._schedule_window_update(hwnd_int)
                except Exception as e:
                    logger.error(f"Error in cloak event callback: {e}")

            self._cloak_callback = WinEventProcType(cloak_event_callback)

            flags = self.WINEVENT_OUTOFCONTEXT | self.WINEVENT_SKIPOWNPROCESS

            cloak_hook = self._user32.SetWinEventHook(
                self.EVENT_OBJECT_CLOAKED, self.EVENT_OBJECT_UNCLOAKED, 0, self._cloak_callback, 0, 0, flags
            )

            if cloak_hook:
                self._win_event_hooks.append(cloak_hook)
            else:
                logger.warning("Failed to set cloak/uncloak event hooks")

        except Exception as e:
            logger.error(f"Failed to set WinEvent hooks: {e}")

    # Hidden window WndProc removed in favor of Qt native event filter

    def _handle_shell_hook_message(self, wparam, lparam):
        """Handle shell hook messages and schedule appropriate updates."""
        try:
            event = wparam
            hwnd_int = int(lparam) if lparam else 0

            if event == self.HSHELL_WINDOWCREATED:
                self._on_window_created(hwnd_int)
            elif event == self.HSHELL_WINDOWDESTROYED:
                self._on_window_destroyed(hwnd_int)
            elif event in (self.HSHELL_WINDOWACTIVATED, self.HSHELL_RUDEAPPACTIVATED):
                self._on_window_activated(hwnd_int)
            elif event == self.HSHELL_REDRAW:
                self._on_window_redraw(hwnd_int)
            elif event == self.HSHELL_FLASH:
                self._on_window_flash(hwnd_int)
            elif event == self.HSHELL_ENDTASK:
                self._on_window_destroyed(hwnd_int)
            elif event == self.HSHELL_WINDOWREPLACING:
                self._on_window_replacing(hwnd_int)
            elif event == self.HSHELL_WINDOWREPLACED:
                self._on_window_replaced(hwnd_int)
            elif event == 16:  # HSHELL_MONITORCHANGED (Windows 8+)
                self._on_window_monitor_changed(hwnd_int)
            else:
                pass

            return 0

        except Exception as e:
            logger.error(f"Error handling shell hook message: {e}")
            return 0

    def _on_window_created(self, hwnd):
        """Add or update a window on creation."""
        try:
            if hwnd in self._windows:
                self._update_window(hwnd)
            else:
                self._add_window(hwnd)
        except Exception as e:
            logger.error(f"Error handling window created for {hwnd}: {e}")

    def _on_window_destroyed(self, hwnd):
        """Remove a window when it’s destroyed."""
        try:
            if hwnd in self._windows:
                self._remove_window(hwnd)
        except Exception as e:
            logger.error(f"Error handling window destroyed for {hwnd}: {e}")

    def _on_window_activated(self, hwnd):
        """Mark activated window active and clear flashing; emit updates for state changes."""
        try:
            foreground_hwnd = self._user32.GetForegroundWindow()

            if not hwnd and foreground_hwnd:
                hwnd = foreground_hwnd

            windows_to_update = set()
            old_states = {}

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

            # if hwnd and hwnd in self._windows:
            #    self._debounce_update(hwnd, delay=60)

        except Exception as e:
            logger.error(f"Error handling window activated for {hwnd}: {e}")

    def _on_window_redraw(self, hwnd):
        """Update or add window on redraw notification."""
        try:
            if hwnd in self._windows:
                # Debounce redraw to avoid reading icon too early (e.g., Explorer folder switch)
                self._debounce_update(hwnd, delay=50)
            else:
                self._add_window(hwnd)
        except Exception as e:
            logger.error(f"Error handling window redraw for {hwnd}: {e}")

    def _on_window_flash(self, hwnd):
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
            logger.error(f"Error handling window flash for {hwnd}: {e}")

    def _on_window_replacing(self, hwnd):
        """Handle replacement by updating if present."""
        if hwnd in self._windows:
            self._update_window(hwnd)

    def _on_window_replaced(self, hwnd):
        """Remove old window on replacement."""
        if hwnd in self._windows:
            self._remove_window(hwnd)

    def _on_window_monitor_changed(self, hwnd):
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
            logger.error(f"Error handling monitor change for {hwnd}: {e}")

    def _on_window_cloaked(self, hwnd):
        """Remove cloaked window from tracking."""
        try:
            if hwnd in self._windows:
                self._remove_window(hwnd)
        except Exception as e:
            logger.error(f"Error handling window cloaked for {hwnd}: {e}")

    def _on_window_uncloaked(self, hwnd):
        """Add or update window when it becomes visible again."""
        try:
            if hwnd not in self._windows:
                self._add_window(hwnd)
            else:
                self._update_window(hwnd)
        except Exception as e:
            logger.error(f"Error handling window uncloaked for {hwnd}: {e}")

    def _add_window(self, hwnd, is_active=False, is_flashing=False):
        """Create and track a window if it should be on the taskbar."""
        try:
            # Validate the handle is a real window
            if not ctypes.windll.user32.IsWindow(hwnd):
                return

            # Create ApplicationWindow instance with exclusion lists
            app_window = ApplicationWindow(hwnd, self._excluded_classes, self._ignored_processes, self._ignored_titles)

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
            logger.error(f"Error adding window {hwnd}: {e}")

    def _delayed_uwp_check(self, hwnd):
        """Retry adding UWP windows after a short delay."""
        try:
            if hwnd in self._windows:
                return

            if not ctypes.windll.user32.IsWindow(hwnd):
                return

            app_window = ApplicationWindow(hwnd, self._excluded_classes, self._ignored_processes, self._ignored_titles)
            if app_window.is_taskbar_window():
                self._windows[hwnd] = app_window
                window_data = app_window.as_dict()
                self.window_added.emit(hwnd, window_data)
        except Exception as e:
            logger.error(f"Delayed UWP check failed for {hwnd}: {e}")

    def _try_add_window_delayed(self, hwnd, delay=50):
        """Try to add a window after a delay (for monitor changes)."""

        def delayed_check():
            try:
                if hwnd in self._windows:
                    return

                if not ctypes.windll.user32.IsWindow(hwnd):
                    return

                app_window = ApplicationWindow(
                    hwnd, self._excluded_classes, self._ignored_processes, self._ignored_titles
                )
                if app_window.is_taskbar_window():
                    self._windows[hwnd] = app_window
                    window_data = app_window.as_dict()
                    self.window_added.emit(hwnd, window_data)
            except Exception as e:
                logger.error(f"Delayed window add failed for {hwnd}: {e}")

        QTimer.singleShot(delay, delayed_check)

    def _remove_window(self, hwnd):
        """Stop tracking a window and emit removal."""
        try:
            if hwnd in self._windows:
                app_window = self._windows[hwnd]
                window_data = app_window.as_dict()
                del self._windows[hwnd]
                self.window_removed.emit(hwnd, window_data)

        except Exception as e:
            logger.error(f"Error removing window {hwnd}: {e}")

    def _update_window(self, hwnd):
        """Update cached data for a window and emit if something changed."""
        try:
            if hwnd in self._windows:
                app_window = self._windows[hwnd]
                old_data = app_window.as_dict()

                app_window.update()

                if not app_window.is_taskbar_window():
                    self._remove_window(hwnd)
                    return

                new_data = app_window.as_dict()

                if old_data != new_data:
                    self.window_updated.emit(hwnd, new_data)

        except Exception as e:
            logger.error(f"Error updating window {hwnd}: {e}")

    def _schedule_window_update(self, hwnd):
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
            logger.debug(f"debounce failed for {hwnd}: {e}")

    def _enumerate_existing_windows(self):
        """Enumerate and track existing windows at startup."""
        try:

            def enum_proc(hwnd, lParam):
                try:
                    self._add_window(hwnd)
                except:
                    pass
                return True

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.POINTER(ctypes.c_long))
            enum_callback = EnumWindowsProc(enum_proc)

            self._user32.EnumWindows(enum_callback, 0)

            foreground_hwnd = self._user32.GetForegroundWindow()
            if foreground_hwnd and foreground_hwnd in self._windows:
                window = self._windows[foreground_hwnd]
                if hasattr(window, "is_active"):
                    window.is_active = True

        except Exception as e:
            logger.error(f"Error enumerating existing windows: {e}")

    def _cleanup_win_event_hooks(self):
        """Uninstall WinEvent hooks."""
        for hook in self._win_event_hooks:
            try:
                self._user32.UnhookWinEvent(hook)
            except:
                pass
        self._win_event_hooks.clear()

    def _unregister_shell_hooks(self):
        """Unregister shell hook window."""
        if self._shell_hook_registered and self._shell_hook_hwnd:
            try:
                self._user32.DeregisterShellHookWindow(self._shell_hook_hwnd)
                self._shell_hook_registered = False
                self._shell_hook_hwnd = None
            except Exception as e:
                logger.error(f"Error unregistering shell hooks: {e}")

    # Hidden window creation/destruction removed

    def get_windows(self) -> Dict[int, ApplicationWindow]:
        """Return a copy of all tracked windows keyed by hwnd."""
        return self._windows.copy()

    def get_window(self, hwnd: int) -> Optional[ApplicationWindow]:
        """Return a tracked window by handle or None."""
        return self._windows.get(hwnd)

    def is_initialized(self) -> bool:
        """True if the manager has started and installed its hooks."""
        return self._initialized

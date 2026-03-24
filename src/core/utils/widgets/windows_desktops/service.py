import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.utils.win32.bindings.user32 import GetClassName, GetForegroundWindow

try:
    from pyvda import (
        AppView,
        VirtualDesktop,
        VirtualDesktopNotificationService,
        get_virtual_desktops,
        set_wallpaper_for_all_desktops,
    )
except Exception:
    AppView = None
    VirtualDesktop = None
    VirtualDesktopNotificationService = None
    get_virtual_desktops = None
    set_wallpaper_for_all_desktops = None

logger = logging.getLogger("windows_desktop_service")

SKIP_WINDOW_CLASSES = frozenset(
    {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
    }
)


class _NotificationHandler:
    """Receives pyvda desktop notification callbacks and forwards them to the service."""

    def __init__(self, service: WindowsDesktopService):
        self._service = service

    def desktop_changed(self, *args):
        self._service._sig_com_desktop_changed.emit()

    def desktop_created(self, *args):
        self._service._sig_com_desktops_updated.emit()

    def desktop_destroyed(self, *args):
        self._service._sig_com_desktops_updated.emit()

    def desktop_moved(self, *args):
        self._service._sig_com_desktops_updated.emit()

    def desktop_renamed(self, *args):
        self._service._sig_com_desktop_renamed.emit()


class WindowsDesktopService(QObject):
    """Service for managing Windows virtual desktops and broadcasting changes."""

    _instance = None
    _init_done = False

    desktop_changed = pyqtSignal(dict)
    desktops_updated = pyqtSignal(dict, dict)

    _sig_com_desktop_changed = pyqtSignal()
    _sig_com_desktops_updated = pyqtSignal()
    _sig_com_desktop_renamed = pyqtSignal()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if WindowsDesktopService._init_done:
            return
        super().__init__()
        WindowsDesktopService._init_done = True
        # Connect internal COM marshaling signals
        self._sig_com_desktop_changed.connect(self._handle_desktop_changed)
        self._sig_com_desktops_updated.connect(self._handle_desktops_updated)
        self._sig_com_desktop_renamed.connect(self._handle_desktop_renamed)
        self._widgets: list = []
        self._timer: QTimer | None = None
        self._notification_cookie: int | None = None
        self._notification_service = None
        self._com_events_active = False
        # Cached state for change detection
        self._desktop_count: int = 0
        self._current_index: int = 0
        try:
            self._desktop_count = len(get_virtual_desktops())
            self._current_index = VirtualDesktop.current().number
        except Exception:
            pass

    def _register_com_notifications(self):
        """Try to register for COM virtual desktop notifications via pyvda."""
        if self._com_events_active:
            return True
        if VirtualDesktopNotificationService is None:
            return False
        try:
            self._notification_service = VirtualDesktopNotificationService()
            handler = _NotificationHandler(self)
            self._notification_cookie = self._notification_service.register(handler)
            self._com_events_active = True
            logger.info("Registered COM virtual desktop event successfully")
            return True
        except Exception:
            logger.warning("Failed to register COM desktop notifications, falling back to polling")
            return False

    def _unregister_com_notifications(self):
        """Unregister the COM notification sink."""
        if not self._com_events_active or self._notification_service is None:
            return
        try:
            self._notification_service.unregister(self._notification_cookie)
        except Exception:
            logger.debug("Failed to unregister COM notifications")
        self._notification_cookie = None
        self._notification_service = None
        self._com_events_active = False

    def _handle_desktop_changed(self):
        """Qt main thread fetch current desktop and emit signal."""
        try:
            current = VirtualDesktop.current().number
        except Exception:
            return
        self._current_index = current
        self.desktop_changed.emit({"index": current})
        # Also refresh in case desktop count changed simultaneously
        self._refresh_state(update_buttons=False)

    def _handle_desktops_updated(self):
        """Refresh desktop list."""
        self._refresh_state(update_buttons=False)

    def _handle_desktop_renamed(self):
        """Refresh with button update for name change."""
        self._refresh_state(update_buttons=True)

    def _refresh_state(self, update_buttons: bool = False):
        """Refresh cached state and emit desktops_updated if changed."""
        try:
            desktop_count = len(get_virtual_desktops())
            current_index = VirtualDesktop.current().number
        except Exception:
            return
        if desktop_count != self._desktop_count or current_index != self._current_index or update_buttons:
            self._desktop_count = desktop_count
            self._current_index = current_index
            self.desktops_updated.emit(
                {"index": current_index},
                {"update_buttons": update_buttons},
            )

    def register_widget(self, widget):
        if widget not in self._widgets:
            self._widgets.append(widget)

        if not self._com_events_active:
            com_ok = self._register_com_notifications()
        else:
            com_ok = True

        # Only start a polling timer if COM notifications failed
        if not com_ok and self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(500)
            self._timer.timeout.connect(self._poll)
            self._timer.start()

    def unregister_widget(self, widget):
        try:
            self._widgets.remove(widget)
        except ValueError:
            pass
        if not self._widgets:
            self._unregister_com_notifications()
            if self._timer:
                self._timer.stop()
                self._timer = None

    def _poll(self):
        self._refresh_state(update_buttons=False)

    def notify_desktop_changed(self, index: int):
        self.desktop_changed.emit({"index": index})

    def notify_desktops_updated(self, update_buttons: bool = False):
        """Force a refresh (e.g. after rename/create/delete)."""
        try:
            current = VirtualDesktop.current().number
        except Exception:
            current = self._current_index
        self._desktop_count = len(get_virtual_desktops())
        self._current_index = current
        self.desktops_updated.emit(
            {"index": current},
            {"update_buttons": update_buttons},
        )

    @staticmethod
    def get_desktops():
        return get_virtual_desktops()

    @staticmethod
    def get_current_desktop():
        return VirtualDesktop.current()

    @staticmethod
    def get_desktop(number: int):
        return VirtualDesktop(number)

    @staticmethod
    def switch_desktop(number: int):
        VirtualDesktop(number).go()

    @staticmethod
    def create_desktop():
        return VirtualDesktop.create()

    @staticmethod
    def remove_desktop(number: int):
        VirtualDesktop(number).remove()

    @staticmethod
    def rename_desktop(number: int, name: str):
        VirtualDesktop(number).rename(name)

    @staticmethod
    def get_desktop_name(number: int) -> str:
        try:
            name = VirtualDesktop(number).name
        except Exception:
            name = ""
        return name.strip() if name else ""

    @staticmethod
    def set_wallpaper(number: int, path: str):
        VirtualDesktop(number).set_wallpaper(path)

    @staticmethod
    def set_wallpaper_all(path: str):
        set_wallpaper_for_all_desktops(path)

    @staticmethod
    def get_foreground_app_view():
        """Return an AppView for the current foreground window, or None
        if the foreground is the desktop, taskbar, or a non-switcher window."""
        try:
            hwnd = GetForegroundWindow()
            if not hwnd:
                return None
            if GetClassName(hwnd) in SKIP_WINDOW_CLASSES:
                return None
            app_view = AppView(hwnd=hwnd)
            if not app_view.is_shown_in_switchers():
                return None
            return app_view
        except Exception:
            return None

    @staticmethod
    def move_window(hwnd: int, desktop_number: int):
        window = AppView(hwnd=hwnd)
        window.move(VirtualDesktop(desktop_number))

    @staticmethod
    def toggle_pin_window(hwnd: int):
        window = AppView(hwnd=hwnd)
        if window.is_pinned():
            window.unpin()
        else:
            window.pin()

    @staticmethod
    def toggle_pin_app(hwnd: int):
        window = AppView(hwnd=hwnd)
        if window.is_app_pinned():
            window.unpin_app()
        else:
            window.pin_app()

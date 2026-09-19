"""Wallpaper watcher service.

Watches the Windows desktop wallpaper and, whenever it changes, extracts a
palette from the new image, saves it to the config directory as CSS, and pokes
the bar to restyle. Opt-in via the root ``wallpaper_colors`` config; modeled on
SystemColorsService, which does the same trick with Windows theme colors.

Three change detectors funnel into one debounced update:

* a native event filter catches the ``WM_SETTINGCHANGE`` broadcast whose
  lParam string is ``ImageColor`` - the instant path, fired by Explorer;
* a timer polls the registry value holding the wallpaper path, so a missed
  broadcast self-heals within a few seconds and even a rewrite of the same
  file is caught (the fingerprint includes the file's mtime and size);
* the ``wallpaper_changed`` event fires for wallpapers set by YASB itself,
  e.g. from the Wallpapers widget.

The only Windows-specific piece is reading the registry wallpaper path, which
is kept in a tiny helper so everything else stays platform-neutral.
"""

import logging
import os

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.events.service import EventService
from core.utils.wallpaper_palette import build_css, extract_palette, write_palette_css
from settings import DEFAULT_CONFIG_DIRECTORY, WALLPAPER_COLORS_FILENAME

logger = logging.getLogger("wallpaper_colors")

_WM_SETTINGCHANGE = 0x001A
# Broadcast by the shell when the desktop wallpaper changes.
_IMAGE_COLOR_STRING = "ImageColor"

# Registry value Windows keeps the current wallpaper path in.
_WALLPAPER_REG_KEY = r"Control Panel\Desktop"
_WALLPAPER_REG_VALUE = "Wallpaper"

# Coalesce bursts of notifications (transitions, per-monitor sets) into one.
_DEBOUNCE_MS = 250
# Catch-all poll, in case a WM_SETTINGCHANGE broadcast is missed.
_POLL_MS = 5000


def _read_registry_wallpaper() -> str | None:
    """The wallpaper path Windows currently has set, or None if unreadable."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WALLPAPER_REG_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _WALLPAPER_REG_VALUE)
            return str(value) or None
    except OSError:
        logger.debug("Could not read current wallpaper from the registry", exc_info=True)
        return None


def _wallpaper_fingerprint(path: str | None) -> tuple | None:
    """Identifies a wallpaper *and* its content: path plus mtime and size.

    Setting the same file again changes nothing, but overwriting a file in
    place keeps its path - only the stat catches that.
    """
    if not path:
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return (path,)
    return (os.path.normcase(path), stat.st_mtime_ns, stat.st_size)


class _SettingChangeFilter(QAbstractNativeEventFilter):
    """Catches the WM_SETTINGCHANGE broadcast that announces a new wallpaper."""

    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change

    def nativeEventFilter(self, eventType, message):  # noqa: N802 - Qt naming
        try:
            if eventType == b"windows_generic_MSG":
                import ctypes
                import ctypes.wintypes

                msg = ctypes.cast(int(message), ctypes.POINTER(ctypes.wintypes.MSG)).contents
                if msg.message == _WM_SETTINGCHANGE and msg.lParam:
                    # lParam is the setting name as a wide string.
                    setting = ctypes.wintypes.LPCWSTR(msg.lParam).value
                    if setting == _IMAGE_COLOR_STRING:
                        self._on_change()
        except Exception:
            logger.debug("Failed to inspect native message", exc_info=True)
        return False, 0


class WallpaperColorsService(QObject):
    """Extracts a palette from the desktop wallpaper and publishes it as CSS."""

    # Connected by main.py to BarManager.styles_modified so the bars restyle.
    stylesheet_changed = pyqtSignal()

    # Fired when YASB itself changes the wallpaper; registered on EventService.
    wallpaper_changed_signal = pyqtSignal(str)

    _instance: WallpaperColorsService | None = None

    @classmethod
    def start_service(cls, auto_apply: bool = True) -> WallpaperColorsService:
        if cls._instance is None:
            cls._instance = cls(auto_apply)
            cls._instance.start()
        return cls._instance

    @classmethod
    def stop_service(cls) -> None:
        if cls._instance is not None:
            cls._instance.stop()
            cls._instance = None

    @classmethod
    def remove_stale_files(cls) -> None:
        """Delete a palette left over from a run where the feature was enabled."""
        try:
            os.remove(cls.css_path())
        except OSError:
            pass

    @staticmethod
    def css_path() -> str:
        return os.path.join(DEFAULT_CONFIG_DIRECTORY, WALLPAPER_COLORS_FILENAME)

    def __init__(self, auto_apply: bool = True):
        super().__init__()
        self._auto_apply = auto_apply
        self._css_path = self.css_path()
        self._last_css: str | None = None
        self._last_fingerprint = None
        self._event_path: str | None = None

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._regenerate)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_MS)
        self._poll_timer.timeout.connect(self._poll_tick)

        self._change_filter = _SettingChangeFilter(self.schedule_update)
        self.wallpaper_changed_signal.connect(self._on_yasb_wallpaper_changed)
        self._event_service = EventService()

    def start(self) -> None:
        app = QApplication.instance()
        if app is None:
            logger.error("Wallpaper colors service requires a running QApplication")
            return
        app.installNativeEventFilter(self._change_filter)
        self._event_service.register_event("wallpaper_changed", self.wallpaper_changed_signal)
        self._poll_timer.start()
        # First palette comes out immediately, then the poll takes over.
        self._poll_tick()
        logger.info("Wallpaper colors service started (auto_apply=%s)", self._auto_apply)

    def stop(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._change_filter)
        self._event_service.unregister_event("wallpaper_changed", self.wallpaper_changed_signal)
        self._poll_timer.stop()
        self._debounce_timer.stop()
        # Revert the auto-apply recolor; get_stylesheet() no longer appends the
        # file once it is gone, so one emit is enough to restore the bar.
        existed = os.path.exists(self._css_path)
        self.remove_stale_files()
        if existed:
            self._last_css = None
            self.stylesheet_changed.emit()
        logger.info("Wallpaper colors service stopped")

    def schedule_update(self) -> None:
        """Queue one palette regeneration, coalescing any number of triggers."""
        self._debounce_timer.start()

    def _on_yasb_wallpaper_changed(self, image_path: str) -> None:
        # The registry may lag a beat behind the shell call, so remember which
        # image YASB set and let the extraction use it directly.
        self._event_path = image_path
        self._last_fingerprint = _wallpaper_fingerprint(image_path)
        self.schedule_update()

    def _poll_tick(self) -> None:
        path = _read_registry_wallpaper()
        fingerprint = _wallpaper_fingerprint(path)
        if fingerprint == self._last_fingerprint:
            return
        self._last_fingerprint = fingerprint
        self.schedule_update()

    def _regenerate(self) -> None:
        """Extract, save and publish the palette of the current wallpaper."""
        wallpaper = _read_registry_wallpaper() or self._event_path
        if not wallpaper:
            logger.debug("No wallpaper path available; skipping palette update")
            return

        try:
            colors = extract_palette(wallpaper)
        except Exception as e:
            logger.warning("Could not extract palette from %s: %s", wallpaper, e)
            return

        if not colors:
            logger.warning("No colors could be extracted from %s", wallpaper)
            return

        css = build_css(colors, auto_apply=self._auto_apply)
        if css == self._last_css:
            return

        if write_palette_css(self._css_path, css):
            self._last_css = css
            self.stylesheet_changed.emit()
            logger.info("Wallpaper palette updated from %s", wallpaper)

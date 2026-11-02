import logging
from typing import Any

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.utils.system import is_windows_10
from core.widgets.services.windows_desktops.service import SHELL_UNAVAILABLE, ForegroundView, WindowsDesktopService


class VirtualDesktops(QObject):
    """The virtual desktops, the one in view and those with windows open, and what can be done with them."""

    desktopsChanged = pyqtSignal()
    foregroundChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._service = WindowsDesktopService()
        self._desktops: list[dict[str, Any]] = []
        self._current = 0
        self._foreground: ForegroundView | None = None
        self._read()
        service = self._service
        service.desktop_changed.connect(self._refresh)
        service.desktops_updated.connect(self._refresh)
        service.populated_changed.connect(self._refresh)
        service.register_widget(self)
        self.destroyed.connect(lambda *_: service.unregister_widget(self))

    def _read(self) -> bool:
        populated = self._service.get_populated_desktops()
        current = self._service.get_current_desktop().number
        desktops = [
            {"number": desktop.number, "name": desktop.name.strip(), "populated": desktop.number in populated}
            for desktop in self._service.get_desktops()
        ]
        if desktops == self._desktops and current == self._current:
            return False
        self._desktops, self._current = desktops, current
        return True

    def _refresh(self, *_: object) -> None:
        if self._read():
            self.desktopsChanged.emit()

    # [{number, name, populated}], numbered from 1 in Task View's order; name is "" until the desktop is renamed
    @qml_property("QVariantList", notify=desktopsChanged)
    def desktops(self) -> list[dict[str, Any]]:
        return self._desktops

    # The desktop in view, or 0 while Explorer isn't answering
    @qml_property(int, notify=desktopsChanged)
    def current(self) -> int:
        return self._current

    @qml_property(bool, constant=True)
    def wallpaperSupported(self) -> bool:
        return not is_windows_10()

    # Whether a window was in front when readForeground() last ran, and whether it or its app is on every desktop
    @qml_property(bool, notify=foregroundChanged)
    def hasWindow(self) -> bool:
        return self._foreground is not None

    @qml_property(bool, notify=foregroundChanged)
    def windowPinned(self) -> bool:
        return self._foreground is not None and self._foreground.pinned

    @qml_property(bool, notify=foregroundChanged)
    def appPinned(self) -> bool:
        return self._foreground is not None and self._foreground.app_pinned

    def _call(self, description: str, action: Any, *args: object) -> None:
        try:
            action(*args)
        except SHELL_UNAVAILABLE:
            logging.warning("Could not %s", description, exc_info=True)

    @pyqtSlot()
    def readForeground(self) -> None:
        """Remembers the window in front, for menu entries that act on it once the menu has taken focus."""
        self._foreground = self._service.get_foreground_app_view()
        self.foregroundChanged.emit()

    @pyqtSlot(int)
    def switchTo(self, number: int) -> None:
        if any(desktop["number"] == number for desktop in self._desktops):
            self._call(f"switch to desktop {number}", self._service.switch_desktop, number)
        else:
            logging.warning("There is no desktop %s to switch to", number)

    @pyqtSlot(int)
    def step(self, offset: int) -> None:
        """Switches by offset desktops, wrapping around at either end."""
        if self._desktops and self._current:
            self.switchTo((self._current - 1 + offset) % len(self._desktops) + 1)

    @pyqtSlot()
    def create(self) -> None:
        self._call("create a desktop", self._service.create_desktop)
        self._service.notify_desktops_updated()

    @pyqtSlot(int)
    def remove(self, number: int) -> None:
        """Deletes desktop number, or the one in view for 0. Its windows move to a neighbouring desktop."""
        self._call(f"delete desktop {number}", self._service.remove_desktop, number or self._current)
        self._service.notify_desktops_updated()

    @pyqtSlot(int, str)
    def rename(self, number: int, name: str) -> None:
        self._call(f"rename desktop {number}", self._service.rename_desktop, number, name.strip())
        self._service.notify_desktops_updated(update_buttons=True)

    @pyqtSlot(int)
    def moveWindowTo(self, number: int) -> None:
        """Moves the window readForeground() found."""
        if self._foreground is not None:
            self._move(self._foreground, number)

    @pyqtSlot(int)
    def moveFrontWindowTo(self, number: int) -> None:
        """Moves the window in front now, for hotkeys and clicks that open no menu."""
        if (view := self._service.get_foreground_app_view()) is not None:
            self._move(view, number)

    def _move(self, view: ForegroundView, number: int) -> None:
        if any(desktop["number"] == number for desktop in self._desktops):
            self._call(f"move a window to desktop {number}", self._service.move_window, view.hwnd, number)
        else:
            logging.warning("There is no desktop %s to move a window to", number)

    @pyqtSlot()
    def toggleWindowPin(self) -> None:
        if self._foreground is not None:
            self._call("pin a window", self._service.toggle_pin_window, self._foreground.hwnd)

    @pyqtSlot()
    def toggleAppPin(self) -> None:
        if self._foreground is not None:
            self._call("pin an app", self._service.toggle_pin_app, self._foreground.hwnd)

    @pyqtSlot(int, QUrl)
    def setWallpaper(self, number: int, image: QUrl) -> None:
        self._call(f"set the wallpaper of desktop {number}", self._service.set_wallpaper, number, image.toLocalFile())

    @pyqtSlot(QUrl)
    def setWallpaperAll(self, image: QUrl) -> None:
        self._call("set the wallpaper of every desktop", self._service.set_wallpaper_all, image.toLocalFile())

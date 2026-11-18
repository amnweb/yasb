from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QWindow

from core.services.taskbar.apps import OpenWindows
from core.utils.icons.image_provider import window_icon_url
from core.utils.icons.service import IconService
from core.utils.qml import qml_property
from core.utils.win32.bindings.user32 import IsIconic, IsWindow, enum_windows
from core.utils.win32.window_actions import (
    close_application,
    force_foreground_focus,
    is_owner_root_active,
    resolve_base_and_focus,
    restore_window,
    set_foreground,
    show_window,
)


class WindowList(QObject):
    """Every window that belongs on a taskbar, front to back, and switching to or closing one.

    It reads the window tracker the taskbar widgets share; windows on other virtual desktops are in it too.
    """

    windowsChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._windows: list[dict[str, Any]] = []
        self._open = OpenWindows.instance()
        self._open.changed.connect(self._publish)
        self._publish()

    # Each window front to back: {hwnd, appId, title, icon, process, className, active, flashing, minimized, cloaked,
    # canMinimize}, icon an image URL; cloaked windows are those on other virtual desktops
    @qml_property("QVariantList", notify=windowsChanged)
    def windows(self) -> list[dict[str, Any]]:
        return self._windows

    def _publish(self) -> None:
        revision = IconService.instance().revision
        order = {hwnd: index for index, hwnd in enumerate(enum_windows())}
        tracked = sorted(self._open.windows.values(), key=lambda window: order.get(window["hwnd"], len(order)))
        windows = [
            {key: value for key, value in window.items() if key != "monitor"}
            | {"icon": window_icon_url(window["hwnd"], revision)}
            for window in tracked
        ]
        if windows != self._windows:
            self._windows = windows
            self.windowsChanged.emit()

    # Whether this window, or a window it owns such as a dialog, is the one in front
    @pyqtSlot(int, result="bool")
    def inFront(self, hwnd: int) -> bool:
        return is_owner_root_active(hwnd)

    # Brings a window to the front, restoring it when minimized, then the dialog it last showed, if any
    @pyqtSlot(int)
    def switchTo(self, hwnd: int) -> None:
        if IsWindow(hwnd):
            # After the popup asking for it has started to close
            QTimer.singleShot(0, lambda: _switch(hwnd))

    # Asks a window to close, as its close button does
    @pyqtSlot(int)
    def close(self, hwnd: int) -> None:
        if IsWindow(hwnd):
            close_application(hwnd)

    # The modifier keys held down right now, as Qt.KeyboardModifier flags
    @pyqtSlot(result="int")
    def keyboardModifiers(self) -> int:
        return QGuiApplication.queryKeyboardModifiers().value

    # Gives a YASB window the foreground and the keyboard, as a popup opened from a hotkey needs
    @pyqtSlot(QWindow)
    def takeFocus(self, window: QWindow) -> None:
        force_foreground_focus(int(window.winId()))


def _switch(hwnd: int) -> None:
    base, focus = resolve_base_and_focus(hwnd)
    if IsIconic(base) or IsIconic(hwnd):
        restore_window(base)
        if base != hwnd:
            restore_window(hwnd)
    else:
        show_window(base)
        if base != hwnd:
            show_window(hwnd)
    set_foreground(base)
    # Some apps take the focus only once restored
    QTimer.singleShot(0, lambda: set_foreground(focus or base))

import logging
import os
from typing import Any

from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PyQt6.QtGui import QWindow
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.utils.win32.dwm import enable_mica
from settings import QML_IMPORT_PATH

_windows: dict[str, QWindow] = {}
_closes_on_quit = False


def show_window(engine: QQmlEngine, type_name: str, properties: dict[str | None, Any]) -> QWindow | None:
    """Shows the window type from Yasb.Common, or brings it forward when it's already open.

    The window owns the objects in properties that have no parent.
    """
    global _closes_on_quit
    window = _windows.get(type_name)
    if window is not None:
        window.raise_()
        window.requestActivate()
        return window
    app = QCoreApplication.instance()
    if app is not None and not _closes_on_quit:
        app.aboutToQuit.connect(close_windows)
        _closes_on_quit = True
    # Not loadFromModule: PyQt keeps the GIL while it waits for Qt's loader thread, which can log through Python
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(os.path.join(QML_IMPORT_PATH, "Yasb", "Common", f"{type_name}.qml"))
    )
    window = component.createWithInitialProperties(properties)
    if not isinstance(window, QWindow):
        logging.error("Could not show %s: %s", type_name, [error.toString() for error in component.errors()])
        return None
    for value in properties.values():
        if isinstance(value, QObject) and value.parent() is None:
            value.setParent(window)
    created = window

    def closed(visible: bool) -> None:
        if not visible and _windows.get(type_name) is created:
            del _windows[type_name]
            created.deleteLater()

    _windows[type_name] = window
    window.visibleChanged.connect(closed)
    enable_mica(int(window.winId()))
    window.show()
    window.requestActivate()
    return window


def close_windows() -> None:
    """Closes every window while its engine still exists, which main deletes after the app quits."""
    for window in list(_windows.values()):
        window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

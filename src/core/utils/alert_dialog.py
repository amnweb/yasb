import logging
from collections.abc import Callable

from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtGui import QWindow
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.utils.win32.bindings.user32 import user32
from core.utils.win32.constants import MB_ICONERROR
from core.utils.win32.dwm import enable_mica
from settings import QML_IMPORT_PATH

# Each alert has an engine of its own, so it shows even when the bars' QML fails to load or no bar exists yet
_alerts: dict[QWindow, QQmlEngine] = {}
# Engines waiting for their deferred delete, kept so Python doesn't delete them first
_closing: set[QQmlEngine] = set()


def show_alert(title: str, message: str, details: str = "", on_closed: Callable[[], None] | None = None) -> None:
    app = QCoreApplication.instance()
    if app is None:
        logging.error("Could not show the alert %r, the application is not running", title)
        return
    if not _alerts and not _closing:
        app.aboutToQuit.connect(close_alerts)
    # A newer alert about the same thing replaces the open one, e.g. while a file is saved again and again
    for open_dialog in [dialog for dialog in _alerts if dialog.property("heading") == title]:
        open_dialog.close()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine)
    component.loadFromModule("Yasb.Common", "AlertDialog")
    dialog = component.createWithInitialProperties({"heading": title, "message": message, "details": details})
    if not isinstance(dialog, QWindow):
        logging.error("Could not show the alert %r: %s", title, [error.toString() for error in component.errors()])
        return

    def closed(visible: bool) -> None:
        if visible or dialog not in _alerts:
            return
        del _alerts[dialog]
        _closing.add(engine)
        engine.destroyed.connect(lambda: _closing.discard(engine))
        dialog.deleteLater()
        engine.deleteLater()
        if on_closed is not None:
            on_closed()

    _alerts[dialog] = engine
    dialog.visibleChanged.connect(closed)
    enable_mica(int(dialog.winId()))
    dialog.show()
    dialog.requestActivate()
    user32.MessageBeep(MB_ICONERROR)


def close_alerts() -> None:
    """Closes every alert and deletes its engine now, which has to happen while Python still runs."""
    for dialog in list(_alerts):
        dialog.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

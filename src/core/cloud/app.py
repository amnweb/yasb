"""YASB Cloud entry point."""

import ctypes
import logging
import os
import sys
import threading
from ctypes import wintypes

from PyQt6 import sip
from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QGuiApplication, QIcon, QWindow
from PyQt6.QtNetwork import QSslSocket
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from core.cloud import logs
from core.cloud.constants import APP_LOG_FILE, TASK_LOG_FILE
from core.utils.win32.dwm import enable_mica
from env import set_qt_quick_defaults
from settings import QML_IMPORT_PATH, SCRIPT_PATH

MUTEX_NAME = "Global\\YASB.Cloud.SingleInstance"
ERROR_ALREADY_EXISTS = 183


def _single_instance() -> bool:
    """Return False if another copy is already running."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            return True
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            return False
        return True
    except Exception:
        return True


def _warm_tls() -> None:
    """Load Qt's TLS backend on a background thread."""

    def load() -> None:
        try:
            QSslSocket.supportsSsl()
        except Exception:
            pass  # only a warm-up, the first request loads it anyway

    threading.Thread(target=load, daemon=True).start()


def main() -> int:
    # Before the mutex and before any widget: a scheduled check must not be skipped because
    # the window happens to be open, and must never build a GUI. Imported here so the normal
    # launch does not pay for it, and the check does not load the UI.
    if "--auto-backup" in sys.argv:
        from core.cloud.run_auto_backup import run_auto_backup

        logs.setup(TASK_LOG_FILE)
        return run_auto_backup()

    logs.setup(APP_LOG_FILE)

    if not _single_instance():
        return 0

    set_qt_quick_defaults()
    app = QGuiApplication(sys.argv)
    app.setApplicationName("YASB Cloud")
    app.setWindowIcon(QIcon(os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")))

    _warm_tls()

    # Imported here rather than at module scope so a scheduled check does not load the whole
    # UI to decide there is nothing to do.
    from core.cloud.ui.cloud import Cloud

    cloud = Cloud()
    engine = QQmlEngine()
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(os.path.join(QML_IMPORT_PATH, "Yasb", "Cloud", "CloudWindow.qml"))
    )
    window = component.createWithInitialProperties({"cloud": cloud})
    if not isinstance(window, QWindow):
        logging.error("Could not open YASB Cloud: %s", [error.toString() for error in component.errors()])
        return 1
    enable_mica(int(window.winId()))
    window.show()
    QTimer.singleShot(0, cloud.start)
    result = app.exec()
    # Qt's own threads can still call into Python while these go, which hangs for good once
    # Python itself is shutting down
    sip.delete(window)
    sip.delete(engine)
    return result


if __name__ == "__main__":
    sys.exit(main())

"""YASB Cloud entry point."""

import ctypes
import sys
import threading
from ctypes import wintypes

from PyQt6.QtNetwork import QSslSocket
from PyQt6.QtWidgets import QApplication

from core.cloud import logs
from core.cloud.constants import APP_LOG_FILE, TASK_LOG_FILE

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

    app = QApplication(sys.argv)
    app.setApplicationName("YASB Cloud")

    _warm_tls()

    # Imported here rather than at module scope so a scheduled check does not load the whole
    # UI to decide there is nothing to do.
    from core.cloud.ui.window import CloudWindow

    window = CloudWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

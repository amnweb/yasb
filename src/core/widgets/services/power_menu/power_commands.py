import logging
import subprocess
from ctypes import WinError
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from core.utils.controller import exit_application
from core.utils.win32.bindings.advapi32 import OpenProcessToken, enable_token_privilege
from core.utils.win32.bindings.kernel32 import CloseHandle, GetCurrentProcess, GetLastError
from core.utils.win32.bindings.powrprof import SetSuspendState
from core.utils.win32.constants import SE_SHUTDOWN_NAME, TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY


@runtime_checkable
class Fadeable(Protocol):
    def fade_out(self) -> None: ...


class PowerOperations:
    def __init__(self, main_window: QWidget | None = None, overlay: QWidget | None = None) -> None:
        self.main_window = main_window
        self.overlay = overlay

    def clear_widget(self) -> None:
        if self.main_window:
            self.main_window.hide()
        if self.overlay:
            self.overlay.hide()

    def _connect_about_to_quit(self, cmd_args: list[str]) -> None:
        """Connect a handler to QCoreApplication.aboutToQuit to run cmd_args."""
        app = QCoreApplication.instance()
        if app is None:
            return

        def _handler():
            try:
                subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

        try:
            app.aboutToQuit.connect(_handler)
        except Exception:
            pass

    def signout(self) -> None:
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/l"])
        exit_application()

    def lock(self) -> None:
        self.clear_widget()
        subprocess.Popen(
            [
                "rundll32.exe",
                "user32.dll,LockWorkStation",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def sleep(self) -> None:
        self.clear_widget()
        try:
            htoken = OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY)
            if htoken:
                try:
                    if not enable_token_privilege(htoken, SE_SHUTDOWN_NAME):
                        raise WinError(GetLastError())
                    success = SetSuspendState(False, True, False)
                    if not success:
                        logging.error("Sleep operation failed")
                finally:
                    CloseHandle(htoken)
            else:
                logging.error("Sleep operation failed to open process token")
        except Exception:
            # Fallback rundll32 method
            try:
                subprocess.Popen(
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "Sleep"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass

    def restart(self) -> None:
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/r", "/t", "0"])
        exit_application()

    def shutdown(self) -> None:
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/s", "/hybrid", "/t", "0"])
        exit_application()

    def force_shutdown(self) -> None:
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/s", "/f", "/t", "0"])
        exit_application()

    def force_restart(self) -> None:
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/r", "/f", "/t", "0"])
        exit_application()

    def hibernate(self) -> None:
        self.clear_widget()
        subprocess.Popen(
            [
                "shutdown",
                "/h",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def cancel(self) -> None:
        if isinstance(self.overlay, Fadeable):
            self.overlay.fade_out()
        if isinstance(self.main_window, Fadeable):
            self.main_window.fade_out()

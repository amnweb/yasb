import ctypes
import logging
import subprocess

import win32api
import win32security
from PyQt6.QtCore import QCoreApplication

from core.utils.controller import exit_application


class PowerOperations:
    def __init__(self, main_window=None, overlay=None):
        self.main_window = main_window
        self.overlay = overlay

    def clear_widget(self):
        if self.main_window:
            self.main_window.hide()
        if self.overlay:
            self.overlay.hide()

    def _connect_about_to_quit(self, cmd_args: list):
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

    def signout(self):
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/l"])
        exit_application()

    def lock(self):
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

    def sleep(self):
        self.clear_widget()
        try:
            access = win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY
            htoken = win32security.OpenProcessToken(win32api.GetCurrentProcess(), access)
            if htoken:
                try:
                    priv_id = win32security.LookupPrivilegeValue(None, win32security.SE_SHUTDOWN_NAME)
                    win32security.AdjustTokenPrivileges(htoken, 0, [(priv_id, win32security.SE_PRIVILEGE_ENABLED)])
                    success = ctypes.windll.powrprof.SetSuspendState(False, True, False)
                    if not success:
                        logging.error("Sleep operation failed")
                finally:
                    win32api.CloseHandle(htoken)
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

    def restart(self):
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/r", "/t", "0"])
        exit_application()

    def shutdown(self):
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/s", "/hybrid", "/t", "0"])
        exit_application()

    def force_shutdown(self):
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/s", "/f", "/t", "0"])
        exit_application()

    def force_restart(self):
        self.clear_widget()
        self._connect_about_to_quit(["shutdown", "/r", "/f", "/t", "0"])
        exit_application()

    def hibernate(self):
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

    def cancel(self):
        if hasattr(self.overlay, "timer"):
            self.overlay.timer.stop()
        if self.overlay:
            self.overlay.fade_out()
        self.main_window.fade_out()

        # Find bar and trigger autohide if applicable
        if hasattr(self.main_window, "parent_button") and self.main_window.parent_button:
            try:
                widget = self.main_window.parent_button
                while widget and not hasattr(widget, "_autohide_bar"):
                    widget = widget.parent()

                if widget and widget._autohide_bar and widget.isVisible():
                    widget._hide_timer.start(widget._autohide_delay)
            except Exception:
                pass

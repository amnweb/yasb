import ctypes
import logging
import os
import shutil
import subprocess
import threading

import win32con
import win32gui
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QSystemTrayIcon

from core.bar_manager import BarManager
from core.ui.views.about import AboutDialog
from core.utils.controller import exit_application, reload_application
from core.utils.shell_utils import shell_open
from core.utils.update_service import register_update_callback
from core.utils.win32.utils import disable_autostart, enable_autostart, is_autostart_enabled
from settings import (
    APP_NAME,
    DEFAULT_CONFIG_DIRECTORY,
    GITHUB_WIKI_URL,
    SCRIPT_PATH,
)

EXE_PATH = os.path.join(SCRIPT_PATH, "yasb.exe")
THEME_EXE_PATH = os.path.join(SCRIPT_PATH, "yasb_themes.exe")
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None


class SystemTrayManager(QSystemTrayIcon):
    _update_signal = pyqtSignal(object)

    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self._bar_manager = bar_manager
        self._icon = QIcon()
        self._update_available = False
        self._pending_release_info = None
        self._load_favicon()
        self.setToolTip(APP_NAME)
        self._load_config()
        self.activated.connect(self._on_tray_activated)
        self._update_signal.connect(self._set_update_badge)
        register_update_callback(self._update_signal.emit)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self._show_context_menu()

    def _load_config(self):
        config = self._bar_manager.config
        self.komorebi_enabled = False
        self.glazewm_enabled = False

        if config and config.komorebi:
            self.komorebi_start = config.komorebi.start_command
            self.komorebi_stop = config.komorebi.stop_command
            self.komorebi_reload = config.komorebi.reload_command
            self.komorebi_enabled = any([self.komorebi_start, self.komorebi_stop, self.komorebi_reload])

        if config and config.glazewm:
            self.glazewm_start = config.glazewm.start_command
            self.glazewm_stop = config.glazewm.stop_command
            self.glazewm_reload = config.glazewm.reload_command
            self.glazewm_enabled = any([self.glazewm_start, self.glazewm_stop, self.glazewm_reload])

    def _load_favicon(self):
        # Get the current directory of the script
        self._icon.addFile(os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png"), QSize(48, 48))
        self.setIcon(self._icon)

    def _set_update_badge(self, release_info=None):
        self._update_available = True
        self._pending_release_info = release_info
        base = QPixmap(os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")).scaled(48, 48)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#ef4747"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(30, 0, 18, 18)
        painter.end()
        self.setIcon(QIcon(base))
        self.setToolTip("Update available")

    def _try_enable_dark_menu(self, hwnd):
        try:
            uxtheme = ctypes.WinDLL("uxtheme.dll")
            uxtheme[135](1)  # undocumented SetPreferredAppMode(AllowDark)
            uxtheme[133](hwnd, True)  # undocumented AllowDarkModeForWindow
            uxtheme[136]()  # undocumented FlushMenuThemes
        except Exception:
            logging.debug("Native dark tray menu unavailable", exc_info=True)

    def _show_context_menu(self):
        """Builds and shows the system tray context menu with dynamic options based on configuration and state."""
        hmenu = None
        selected_action = None
        try:
            hmenu = win32gui.CreatePopupMenu()
            actions = {}
            cmd_id = [1]

            def add_item(menu, label, action):
                win32gui.AppendMenu(menu, win32con.MF_STRING, cmd_id[0], label)
                actions[cmd_id[0]] = action
                cmd_id[0] += 1

            def add_sep(menu):
                win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")

            if self._update_available:
                add_item(hmenu, "Update Available", self._open_update_dialog)
                add_sep(hmenu)

            add_item(hmenu, "Open Config", self._open_config)
            if os.path.exists(THEME_EXE_PATH):
                add_item(hmenu, "Get Themes", lambda: os.startfile(THEME_EXE_PATH))
            add_item(hmenu, "Reload YASB", self._reload_application)
            add_sep(hmenu)

            if self.komorebi_enabled and self.is_wm_installed("komorebi"):
                km_sub = win32gui.CreatePopupMenu()
                if self.komorebi_start:
                    add_item(km_sub, "Start Komorebi", lambda: self._run_wm_command("Komorebi", self.komorebi_start))
                if self.komorebi_stop:
                    add_item(km_sub, "Stop Komorebi", lambda: self._run_wm_command("Komorebi", self.komorebi_stop))
                if self.komorebi_reload:
                    add_item(km_sub, "Reload Komorebi", lambda: self._run_wm_command("Komorebi", self.komorebi_reload))
                win32gui.AppendMenu(hmenu, win32con.MF_POPUP, km_sub, "Komorebi")
                add_sep(hmenu)

            if self.glazewm_enabled and self.is_wm_installed("glazewm"):
                gw_sub = win32gui.CreatePopupMenu()
                if self.glazewm_start:
                    add_item(gw_sub, "Start GlazeWM", lambda: self._run_wm_command("Glazewm", self.glazewm_start))
                if self.glazewm_stop:
                    add_item(gw_sub, "Stop GlazeWM", lambda: self._run_wm_command("Glazewm", self.glazewm_stop))
                if self.glazewm_reload:
                    add_item(gw_sub, "Reload GlazeWM", lambda: self._run_wm_command("Glazewm", self.glazewm_reload))
                win32gui.AppendMenu(hmenu, win32con.MF_POPUP, gw_sub, "GlazeWM")
                add_sep(hmenu)

            if AUTOSTART_FILE:
                if self._check_startup():
                    add_item(hmenu, "Disable Autostart", self._disable_startup)
                else:
                    add_item(hmenu, "Enable Autostart", self._enable_startup)

            add_item(hmenu, "Help", lambda: self._open_in_browser(GITHUB_WIKI_URL))
            add_item(hmenu, "About", self._show_about_dialog)
            add_sep(hmenu)
            add_item(hmenu, "Exit", self._exit_application)

            bars = self._bar_manager.bars
            hwnd = int(bars[0].winId()) if bars else win32gui.GetDesktopWindow()
            x, y = win32gui.GetCursorPos()
            self._try_enable_dark_menu(hwnd)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                logging.debug("Failed to set tray menu owner as foreground window", exc_info=True)
            cmd = win32gui.TrackPopupMenu(
                hmenu,
                win32con.TPM_LEFTALIGN | win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
                x,
                y,
                0,
                hwnd,
                None,
            )
            selected_action = actions.get(cmd)
            try:
                win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
            except Exception:
                logging.debug("Failed to post tray menu cleanup message", exc_info=True)
        except Exception:
            logging.exception("Failed to show context menu")
        finally:
            if hmenu:
                win32gui.DestroyMenu(hmenu)

        if selected_action:
            try:
                selected_action()
            except Exception:
                logging.exception("Tray menu action failed")

    def is_wm_installed(self, wm) -> bool:
        try:
            wm_path = shutil.which(wm)
            return wm_path is not None
        except Exception as e:
            logging.error("Error checking %s installation: %s", wm, e)
            return False

    def _enable_startup(self):
        enable_autostart(APP_NAME, AUTOSTART_FILE)

    def _disable_startup(self):
        disable_autostart(APP_NAME)

    def _check_startup(self) -> bool:
        return bool(is_autostart_enabled(APP_NAME))

    def _open_config(self):
        try:
            subprocess.run(["explorer", DEFAULT_CONFIG_DIRECTORY])
        except Exception as e:
            logging.error("Failed to open config directory: %s", e)

    def _run_wm_command(self, wm, command):
        def wm_command():
            try:
                subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                logging.error("Failed to start %s: %s", wm, e)

        threading.Thread(target=wm_command).start()

    def _reload_application(self):
        reload_application("Reloading Application from tray...")

    def _exit_application(self):
        exit_application("Exiting Application from tray...")

    def _open_in_browser(self, url):
        try:
            shell_open(url)
        except Exception as e:
            logging.error("Failed to open browser: %s", e)

    def _show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _open_update_dialog(self):
        from core.ui.views.updater import UpdateDialog

        dialog = UpdateDialog(release_info=self._pending_release_info)
        dialog.exec()

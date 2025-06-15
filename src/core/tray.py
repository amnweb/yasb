import logging
import os
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from core.bar_manager import BarManager
from core.config import get_config
from core.utils.controller import exit_application, reload_application
from core.utils.win32.utilities import disable_autostart, enable_autostart, is_autostart_enabled
from settings import (
    APP_NAME,
    APP_NAME_FULL,
    BUILD_VERSION,
    DEFAULT_CONFIG_DIRECTORY,
    GITHUB_THEME_URL,
    GITHUB_URL,
    SCRIPT_PATH,
)

OS_STARTUP_FOLDER = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
VBS_PATH = os.path.join(SCRIPT_PATH, "yasb.vbs")
EXE_PATH = os.path.join(SCRIPT_PATH, "yasb.exe")
THEME_EXE_PATH = os.path.join(SCRIPT_PATH, "yasb_themes.exe")
SHORTCUT_FILENAME = "yasb.lnk"
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else VBS_PATH


class SystemTrayManager(QSystemTrayIcon):
    def __init__(self, bar_manager: BarManager):
        super().__init__()
        self._bar_manager = bar_manager
        self._icon = QIcon()
        self._load_favicon()
        self.setToolTip(APP_NAME)
        self._load_config()
        self._remove_shortcut()
        self.activated.connect(self._on_tray_activated)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if self.menu and self.menu.isVisible():
                global_pos = event.globalPosition().toPoint()
                all_menus = [self.menu]
                all_menus += [act.menu() for act in self.menu.actions() if act.menu() and act.menu().isVisible()]
                if not any(m.geometry().contains(global_pos) for m in all_menus):
                    self.menu.hide()
                    self.menu.deleteLater()
                    return True
        return super().eventFilter(obj, event)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self._load_context_menu()
            self.menu.popup(QCursor.pos())
            self.menu.activateWindow()

    def _load_config(self):
        try:
            config = get_config(show_error_dialog=True)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return
        if config["komorebi"]:
            self.komorebi_start = config["komorebi"]["start_command"]
            self.komorebi_stop = config["komorebi"]["stop_command"]
            self.komorebi_reload = config["komorebi"]["reload_command"]

    def _load_favicon(self):
        # Get the current directory of the script
        self._icon.addFile(os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png"), QSize(48, 48))
        self.setIcon(self._icon)

    def _load_context_menu(self):
        self.menu = QMenu()
        self.menu.setWindowModality(Qt.WindowModality.WindowModal)

        style_sheet = """
        QMenu {
            background-color: #26292b;
            color: #ffffff;
            border:1px solid #373b3e;
            padding:5px 0;
            margin:0;
            border-radius:4px
        }
        QMenu::item {
            margin:0 4px;
            padding: 4px 24px 5px 24px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'Segoe UI', sans-serif;
        }
        QMenu::item:selected {
            background-color: #373b3e;
        }
        QMenu::separator {
            height: 1px;
            background: #373b3e;
            margin:5px 0;
        }
        QMenu::right-arrow {
            width: 8px;
            height: 8px;
            padding-right:24px;
        }
        """
        self.menu.setStyleSheet(style_sheet)

        open_config_action = self.menu.addAction("Open Config")
        open_config_action.triggered.connect(self._open_config)
        if os.path.exists(THEME_EXE_PATH):
            yasb_themes_action = self.menu.addAction("Get Themes")
            yasb_themes_action.triggered.connect(lambda: os.startfile(THEME_EXE_PATH))

        reload_action = self.menu.addAction("Reload YASB")
        reload_action.triggered.connect(self._reload_application)
        self.reload_action = reload_action

        self.menu.addSeparator()
        if self.is_komorebi_installed():
            komorebi_menu = self.menu.addMenu("Komorebi")
            start_komorebi = komorebi_menu.addAction("Start Komorebi")
            start_komorebi.triggered.connect(self._start_komorebi)

            stop_komorebi = komorebi_menu.addAction("Stop Komorebi")
            stop_komorebi.triggered.connect(self._stop_komorebi)

            reload_komorebi = komorebi_menu.addAction("Reload Komorebi")
            reload_komorebi.triggered.connect(self._reload_komorebi)

            self.menu.addSeparator()

        if self._chek_startup():
            disable_startup_action = self.menu.addAction("Disable Autostart")
            disable_startup_action.triggered.connect(self._disable_startup)
        else:
            enable_startup_action = self.menu.addAction("Enable Autostart")
            enable_startup_action.triggered.connect(self._enable_startup)

        help_action = self.menu.addAction("Help")
        help_action.triggered.connect(lambda: self._open_in_browser(f"{GITHUB_URL}/wiki"))

        about_action = self.menu.addAction("About")
        about_action.triggered.connect(self._show_about_dialog)

        self.menu.addSeparator()
        exit_action = self.menu.addAction("Exit")
        exit_action.triggered.connect(self._exit_application)

    def is_komorebi_installed(self):
        try:
            komorebi_path = shutil.which("komorebi")
            return komorebi_path is not None
        except Exception as e:
            logging.error(f"Error checking komorebi installation: {e}")
            return False

    def _remove_shortcut(self):
        # Backward compatibility for old versions, this should be removed in future releases
        # Check if the shortcut file exists in the startup folder and remove it if it does
        shortcut_path = os.path.join(OS_STARTUP_FOLDER, SHORTCUT_FILENAME)
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
            except FileNotFoundError:
                logging.warning(f"Shortcut file not found: {shortcut_path}")
            except PermissionError:
                logging.error(f"Permission denied while trying to remove shortcut: {shortcut_path}")
            except Exception as e:
                logging.error(f"An unexpected error occurred while removing shortcut: {e}")

    def _enable_startup(self):
        enable_autostart(APP_NAME, AUTOSTART_FILE)

    def _disable_startup(self):
        disable_autostart(APP_NAME)

    def _chek_startup(self):
        if is_autostart_enabled(APP_NAME):
            return True
        else:
            return False

    def _open_config(self):
        try:
            subprocess.run(["explorer", str(os.path.join(Path.home(), DEFAULT_CONFIG_DIRECTORY))])
        except Exception as e:
            logging.error(f"Failed to open config directory: {e}")

    def _start_komorebi(self):
        def run_komorebi_start():
            try:
                subprocess.run(self.komorebi_start, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
            except Exception as e:
                logging.error(f"Failed to start komorebi: {e}")

        threading.Thread(target=run_komorebi_start).start()

    def _stop_komorebi(self):
        def run_komorebi_stop():
            try:
                subprocess.run(self.komorebi_stop, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
            except Exception as e:
                logging.error(f"Failed to stop komorebi: {e}")

        threading.Thread(target=run_komorebi_stop).start()

    def _reload_komorebi(self):
        def run_komorebi_reload():
            try:
                subprocess.run(self.komorebi_reload, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
            except Exception as e:
                logging.error(f"Failed to reload komorebi: {e}")

        threading.Thread(target=run_komorebi_reload).start()

    def _reload_application(self):
        reload_application("Reloading Application from tray...")

    def _exit_application(self):
        exit_application("Exiting Application from tray...")

    def _open_in_browser(self, url):
        try:
            webbrowser.open(url)
        except Exception as e:
            logging.error(f"Failed to open browser: {e}")

    def _show_about_dialog(self):
        about_box = QMessageBox()
        about_box.setWindowTitle("About YASB")
        icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
        icon = QIcon(icon_path)
        about_box.setStyleSheet("QLabel#qt_msgboxex_icon_label { margin: 10px 10px 10px 20px; }")
        about_box.setIconPixmap(icon.pixmap(64, 64))
        about_box.setWindowIcon(icon)
        about_text = f"""
        <div style="font-family:'Segoe UI'">
        <div style="font-size:24px;font-weight:400;margin-right:60px"><span style="font-weight:bold">YASB</span> Reborn</div>
        <div style="font-size:13px;font-weight:600;margin-top:8px">{APP_NAME_FULL}</div>
        <div style="font-size:13px;font-weight:600;">Version: {BUILD_VERSION}</div><br>
        <div style="margin-top:5px;font-size:13px;font-weight:600;"><a style="text-decoration:none" href="{GITHUB_URL}">YASB on GitHub</a></div>
        <div style="margin-top:5px;font-size:13px;font-weight:600;"><a style="text-decoration:none" href="{GITHUB_THEME_URL}">YASB Themes</a></div>
        <div style="margin-top:5px;font-size:13px;font-weight:600;"><a style="text-decoration:none" href="https://discord.gg/qkeunvBFgX">Join Discord</a></div>
        </div>
        """
        about_box.setText(about_text)
        about_box.setStandardButtons(QMessageBox.StandardButton.Close)
        about_box.exec()
